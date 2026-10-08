import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

from openai import OpenAI, OpenAIError

LOG_DIR = Path(__file__).parent / "logs" / "hw01"
EXIT_COMMAND = "/exit"
MARKER = "$function$"
CALL = re.compile(rf"{re.escape(MARKER)}\s*(\w+)\s*\((.*?)\)\s*{re.escape(MARKER)}", re.DOTALL)
MAX_STEPS = 5

log = logging.getLogger(__name__)

# a sample thesis with deliberate violations; reading real docx files is not part of this task
THESIS = {
    "margins": {"left_mm": 25, "right_mm": 10, "top_mm": 20, "bottom_mm": 20},
    "text": {
        "font": "Times New Roman",
        "size_pt": 14,
        "line_spacing": 1.0,
        "first_line_indent_cm": 1.25,
        "alignment": "justify",
    },
    "headings": [
        "Содержание",
        "Введение",
        "1 Анализ предметной области",
        "1.1 Обзор существующих решений.",
        "1.2 Постановка задачи",
        "2 Проектирование системы",
        "2.1 Архитектура системы",
        "Список использованной литературы",
    ],
    "bibliography": [
        "Петров, А. В. Проектирование информационных систем / А. В. Петров. "
        "– М. : Наука, 2021. – 312 с.",
        "Smith, J. Document Processing Pipelines / J. Smith. "
        "– London : Example Press, 2020. – 250 p.",
        "Алексеев, Б. Г. Обработка текстов на естественном языке / Б. Г. Алексеев. "
        "– СПб. : Питер, 2022. – 288 с.",
        "Документация Python [Электронный ресурс]. "
        "– Режим доступа: https://docs.python.org/3/, свободный.",
    ],
}

# excerpts from the university guidelines; the original documents are kept outside git in data/
REQUIREMENTS = {
    "margins": [
        {
            "text": (
                "Текст ВКР следует печатать, соблюдая следующие размеры полей: "
                "левое - 30 мм, правое - 10 мм, верхнее и нижнее - 20 мм."
            ),
            "source": "Требования к ВКР ИИТ 2019, п. 5.7.2",
        },
    ],
    "text": [
        {
            "text": (
                "Текст ВКР набирается полуторным интервалом. Цвет шрифта должен быть черным, "
                "шрифт - Times New Roman, размер 14, полужирный шрифт не применяется. "
                "Отступ красной строки 1,25 см, выравнивание по ширине без переносов."
            ),
            "source": "Требования к ВКР ИИТ 2019, п. 5.7.1",
        },
    ],
    "headings": [
        {
            "text": (
                "Структура ВКР должна включать: титульный лист (Приложение 3); содержание; "
                "введение; основную часть; заключение; список использованной литературы; "
                "приложения (при необходимости)."
            ),
            "source": "Требования к ВКР ИИТ 2019, п. 5.1",
        },
        {
            "text": (
                "Заголовки структурных элементов ВКР печатаются с первой прописной буквы "
                "без точки в конце. Размер шрифта заголовка должен совпадать с размером шрифта "
                "основного текста. Разделы основной части ВКР должны быть пронумерованы "
                "арабскими цифрами в пределах всей ВКР. Заголовки разделов «Содержание», "
                "«Введение», «Заключение» и «Список использованной литературы» не нумеруются. "
                "Номер подраздела (пункта) должен состоять из номера раздела и номера "
                "подраздела, разделенных точкой."
            ),
            "source": "Требования к ВКР ИИТ 2019, п. 5.7.3",
        },
    ],
    "bibliography": [
        {
            "text": (
                "Список использованной литературы оформляется в соответствии с ГОСТ 7.1-2003 "
                "(Библиографическая запись. Библиографическое описание. Общие требования "
                "и правила составления)."
            ),
            "source": "Требования к ВКР ИИТ 2019, п. 5.7.7",
        },
        {
            "text": (
                "Список литературы оформляется как нумерованный список арабскими цифрами "
                "с абзацного отступа – 1,25. Список должен включать не менее 20 источников. "
                "Все источники размещают строго в алфавитном порядке. ... В первую очередь "
                "размещают источники на русском языке, после них следует иностранная "
                "литература."
            ),
            "source": "Оформление ВКР ИИТ 2025, слайд 14",
        },
    ],
}


def get_thesis(topic: str) -> dict | list:
    return by_topic(THESIS, topic)


def get_requirements(topic: str) -> list[dict[str, str]]:
    return by_topic(REQUIREMENTS, topic)


def by_topic(table: dict, topic: str) -> dict | list:
    if topic not in table:
        raise ValueError(f"unknown topic {topic!r}, expected one of: {', '.join(table)}")
    return table[topic]


FUNCTIONS = {"get_thesis": get_thesis, "get_requirements": get_requirements}


def find_call(reply: str) -> tuple[str, str] | None:
    """Returns the name and the argument of the first function call in the reply."""
    match = CALL.search(reply)
    if match is None:
        return None
    name, argument = match.groups()
    # the format has no argument names or quotes, but models add them now and then
    return name, argument.rpartition("=")[2].strip().strip("\"'")


def call_function(name: str, argument: str) -> str:
    """Runs a call from the reply; errors go back to the model so that it can fix the call."""
    function = FUNCTIONS.get(name)
    if function is None:
        return f"error: unknown function {name}, expected one of: {', '.join(FUNCTIONS)}"
    try:
        return json.dumps(function(argument), ensure_ascii=False)
    except ValueError as e:
        return f"error: {e}"


PROMPT_CHAT = """\
You are a consultant on formatting graduation theses (ВКР) at a Russian university.

<task>
Answer the student's questions about thesis formatting.
</task>

<rules>
- Answer briefly and to the point: no introductions, no general advice.
- Give the usual requirement and note that the university guidelines have the final say.
- Always answer in Russian.
</rules>"""

PROMPT_V1 = """\
You are an assistant that checks a thesis against the university formatting requirements.

<task>
Answer the user's questions about the thesis.
</task>

<functions>
- get_thesis(topic: str): Part of the thesis under check: margins, text, headings or bibliography.
- get_requirements(topic: str): University requirements with sources on margins, text, \
headings or bibliography.
</functions>

<call_format>
When you need data from a function, reply with the call only:
$function$get_requirements(margins)$function$
The result will come in the next message.
</call_format>

<rules>
- Always answer in Russian.
</rules>"""

PROMPT_V2 = """\
You are a normcontrol assistant: you check a student's thesis against the university \
formatting requirements.

<task>
Check the thesis on the topic the user asks about, step by step:
1. Call get_thesis(topic) to see how the thesis is formatted.
2. Call get_requirements(topic) to get the requirements.
3. Compare the two and answer.
Topics: margins, text, headings (also the list of sections), bibliography.
</task>

<functions>
- get_thesis(topic: str): Part of the thesis under check: margins, text, headings or bibliography.
- get_requirements(topic: str): University requirements with sources on margins, text, \
headings or bibliography.
</functions>

<call_format>
To call a function, reply with the call only, one call per reply:
$function$get_thesis(margins)$function$
The result comes in the next message, starting with "Result of".
</call_format>

<rules>
- Take the thesis data only from get_thesis, never ask the user for it.
- Answer only when you have both the thesis data and the requirements on the topic.
- For each violation give the value in the thesis, the required value and the source.
- If nothing is violated, say so in one sentence.
- Do not report anything the function results do not show.
- Always answer in Russian.
</rules>

<example>
User: Проверь поля страницы.
Assistant: $function$get_thesis(margins)$function$
User: Result of get_thesis(margins): {"left_mm": 30, "right_mm": 15, "top_mm": 20, \
"bottom_mm": 20}
Assistant: $function$get_requirements(margins)$function$
User: Result of get_requirements(margins): [{"text": "Текст ВКР следует печатать, соблюдая \
следующие размеры полей: левое - 30 мм, правое - 10 мм, верхнее и нижнее - 20 мм.", \
"source": "Требования к ВКР ИИТ 2019, п. 5.7.2"}]
Assistant: Правое поле 15 мм, а требуется 10 мм (Требования к ВКР ИИТ 2019, п. 5.7.2). \
Остальные поля соответствуют.
</example>"""

PROMPT_V3 = """\
You are a normcontrol assistant: you check a student's thesis against the university \
formatting requirements.

<task>
Answer by checking the thesis in three steps:
1. Reply with a call to get_thesis(topic).
2. After its result, reply with a call to get_requirements(topic). Do it for every question: \
requirements on another topic earlier in the dialogue do not count.
3. After its result, go through the requirements one by one and answer with a line per \
requirement: what is required, what the thesis has, and «соответствует» or «нарушение». \
End with the source of the requirements.
Topics: margins (page margins), text (font, size, line spacing, indent), headings (headings \
and the list of sections), bibliography (reference list).
</task>

<functions>
- get_thesis(topic: str): Part of the thesis under check: margins, text, headings or bibliography.
- get_requirements(topic: str): University requirements with sources on margins, text, \
headings or bibliography.
</functions>

<call_format>
To call a function, reply with the call only, one call per reply:
$function$get_thesis(margins)$function$
The result comes in the next message, starting with "Result of".
</call_format>

<rules>
- Never write function results yourself, they come only in messages starting with "Result of".
- Take the thesis data only from get_thesis, never ask the user for it.
- Write the values of the thesis exactly as get_thesis returns them. Line spacing 1.0 is \
single, 1.5 is one and a half (полуторный).
- Answer only when you have both the thesis data and the requirements on the topic.
- Do not report anything the function results do not show.
- Always answer in Russian.
</rules>

<example>
For the question «Проверь поля страницы.» the first reply is \
$function$get_thesis(margins)$function$, after its result the second reply is \
$function$get_requirements(margins)$function$, and if the thesis has margins of 30, 15, 20 \
and 20 mm, the final answer is:
- левое поле: требуется 30 мм, в работе 30 мм — соответствует
- правое поле: требуется 10 мм, в работе 15 мм — нарушение
- верхнее поле: требуется 20 мм, в работе 20 мм — соответствует
- нижнее поле: требуется 20 мм, в работе 20 мм — соответствует
Источник: Требования к ВКР ИИТ 2019, п. 5.7.2.
</example>"""

PROMPT_V4 = """\
You are a normcontrol assistant: you check a student's thesis against the university \
formatting requirements.

<task>
Answer every question about the thesis in three replies, in this order:
Reply 1, the thesis data:
$function$get_thesis(topic)$function$
Reply 2, the requirements on the same topic:
$function$get_requirements(topic)$function$
Reply 3, the check: a line per check with what the thesis has (copy it from the get_thesis \
result), what is required, and «соответствует», «нарушение» or «нет данных». End with the \
sources of the requirements.
Make all three replies for every question, even if the dialogue already has data on the topic.
</task>

<topics>
- margins: поля страницы. Check every margin.
- text: шрифт, размер шрифта, межстрочный интервал, отступ, выравнивание основного текста. \
Check every value.
- headings: заголовки, разделы, структура работы. Check that every required section is in the \
list and that every heading follows the rules for headings.
- bibliography: список литературы, источники. Check the number of references, their order and \
how each one is written.
</topics>

<functions>
- get_thesis(topic: str): Part of the thesis under check: margins, text, headings or bibliography.
- get_requirements(topic: str): University requirements with sources on margins, text, \
headings or bibliography.
</functions>

<call_format>
To call a function, reply with the call only, one call per reply:
$function$get_thesis(margins)$function$
The result comes in the next message, starting with "Result of".
</call_format>

<rules>
- Never write function results yourself, they come only in messages starting with "Result of".
- Take the thesis data only from get_thesis, never ask the user for it.
- Write the values of the thesis exactly as get_thesis returns them. Line spacing 1.0 is \
single, 1.5 is one and a half (полуторный).
- «нарушение» means the thesis differs from the requirement, «нет данных» means the get_thesis \
result has nothing on the check.
- Always answer in Russian.
</rules>

<example>
For the question «Проверь поля страницы.» reply 1 is $function$get_thesis(margins)$function$, \
reply 2 is $function$get_requirements(margins)$function$, and if the thesis has margins of 30, \
15, 20 and 20 mm, reply 3 is:
- левое поле: в работе 30 мм, требуется 30 мм — соответствует
- правое поле: в работе 15 мм, требуется 10 мм — нарушение
- верхнее поле: в работе 20 мм, требуется 20 мм — соответствует
- нижнее поле: в работе 20 мм, требуется 20 мм — соответствует
Источник: Требования к ВКР ИИТ 2019, п. 5.7.2.
</example>"""

PROMPTS = {
    "chat": PROMPT_CHAT,
    "v1": PROMPT_V1,
    "v2": PROMPT_V2,
    "v3": PROMPT_V3,
    "v4": PROMPT_V4,
}


class Assistant:
    """Chat with history that runs the functions the model calls in its replies."""

    def __init__(
        self, client: OpenAI, model: str, system_prompt: str, temperature: float, max_tokens: int
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.history = [{"role": "system", "content": system_prompt}]

    def ask(self, question: str) -> None:
        log.info("user: %s", question)

        turn = [{"role": "user", "content": question}]
        for _ in range(MAX_STEPS):
            reply = self._complete(self.history + turn)
            call = find_call(reply)
            if call is None:
                if MARKER in reply:
                    log.warning("the reply has a marker but no valid call")
                self.history += [*turn, {"role": "assistant", "content": reply}]
                return
            name, argument = call
            result = call_function(name, argument)
            log.info("call %s(%s) -> %s", name, argument, result)
            print(f"-> {result}")
            # text around the call is dropped: after the call the model can only guess the result
            turn += [
                {"role": "assistant", "content": f"{MARKER}{name}({argument}){MARKER}"},
                {"role": "user", "content": f"Result of {name}({argument}): {result}"},
            ]
        log.warning("no answer after %d function calls", MAX_STEPS)
        print(f"(no answer after {MAX_STEPS} function calls)")

    def _complete(self, messages: list[dict[str, str]]) -> str:
        """Prints the reply as it streams and returns it."""
        started = time.perf_counter()
        parts = []
        finish_reason = None
        with self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        ) as stream:
            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.delta.content:
                    print(choice.delta.content, end="", flush=True)
                    parts.append(choice.delta.content)
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        print()
        reply = "".join(parts)
        log.info("assistant (%.1f s): %s", time.perf_counter() - started, reply)
        if finish_reason == "length":
            log.warning("the reply was cut off at max_tokens")
        return reply


def connect() -> tuple[OpenAI, str]:
    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1"),
        # llama-server needs no key, but the SDK refuses to start without one
        api_key=os.getenv("LLM_API_KEY", "none"),
    )
    # llama-server serves a single model and reports its id
    model = os.getenv("LLM_MODEL") or client.models.list().data[0].id
    return client, model


def setup_logging(model: str, prompt: str) -> None:
    # "models/qwen2.5-3b-instruct-q4_k_m.gguf" -> "qwen2.5-3b-instruct-q4_k_m"
    name = re.sub(r"[^\w.-]", "-", Path(model).name.removesuffix(".gguf"))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / f"{name}.{prompt}.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # the SDK logs every HTTP request, which only repeats the assistant's own records
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def repl(assistant: Assistant) -> None:
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if question == EXIT_COMMAND:
            return
        if not question:
            continue
        try:
            assistant.ask(question)
        except KeyboardInterrupt:  # Ctrl+C during an answer cancels only the answer
            log.warning("answer interrupted")
            print("\n(interrupted)")
        except OpenAIError as e:
            log.error("request failed: %s", e)
            print(f"\nerror: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Console chat; with a v* prompt it checks a thesis by calling functions.",
        epilog=(
            "The model is set by LLM_BASE_URL, LLM_API_KEY and LLM_MODEL. "
            f"{EXIT_COMMAND} or Ctrl+D quits."
        ),
    )
    parser.add_argument("--prompt", choices=PROMPTS, default="v4")
    parser.add_argument("-t", "--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()

    try:
        client, model = connect()
    except OpenAIError as e:
        sys.exit(f"error: {e}")
    print(f"model: {model}")
    setup_logging(model, args.prompt)
    log.info(
        "model %s, prompt %s, temperature %s, max_tokens %s",
        model,
        args.prompt,
        args.temperature,
        args.max_tokens,
    )
    repl(Assistant(client, model, PROMPTS[args.prompt], args.temperature, args.max_tokens))


if __name__ == "__main__":
    main()
