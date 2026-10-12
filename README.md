# csu-ai-agents

## Содержание

- [Задание 01](#задание-01)
  - [Развёртывание LLM — Домашнее задание](#развёртывание-llm--домашнее-задание)
  - [Домашнее задание](#домашнее-задание)
- [Задание 02](#задание-02)
  - [Чат-агент на LangChain с памятью в файле](#чат-агент-на-langchain-с-памятью-в-файле)

## Задание 01

### Развёртывание LLM — Домашнее задание

1. Запустить maple-preview на CPU через llama.cpp, замерить токены/с

    ```shell
    llama serve -m models/maple-preview-TQ1_0-head-F16.gguf -dev none
    ```
    <details><summary>Output</summary>

    ```
    0.00.001.521 I srv  llama_server: initializing ...
    0.00.038.872 I cmn  common_param: common_params_print_info: verbosity = 3 (adjust with the `-lv N` CLI arg)
    0.00.039.032 W srv  llama_server: security: no API key is set and CORS allows all origins (see https://github.com/ggml-org/llama.cpp/pull/25655)
    0.00.040.357 I srv    load_model: loading model 'models/maple-preview-TQ1_0-head-F16.gguf'
    0.00.284.378 W load: control-looking token: 128247 '</s>' was not control-type; this is probably a bug in the model. its type will be overridden
    0.02.105.466 I cmn          init: llama threadpool init, n_threads = 6
    0.02.746.184 I srv    load_model: initializing, n_slots = 4, n_ctx_slot = 131072, kv_unified = 'true'
    0.02.749.758 W srv          init: chat template supports preserving reasoning, it is enabled by default (may use more tokens, disable via --no-reasoning-preserve)
    0.02.749.763 I srv  llama_server: model loaded
    0.02.749.764 I srv  llama_server: listening on http://127.0.0.1:8080
    0.02.749.764 W srv  llama_server: notice: server default port will be changed to :9931 in a future release (ref: https://github.com/ggml-org/llama.cpp/pull/26508)
    ```

    </details>

    ```shell
    llama bench -m models/maple-preview-TQ1_0-head-F16.gguf -dev none
    ```
    <details><summary>Output</summary>

    ```
    ggml_vulkan: Found 1 Vulkan devices:
    ggml_vulkan: 0 = Intel(R) UHD Graphics 730 (ADL-S GT1) (Intel open-source Mesa driver) | uma: 1 | fp16: 1 | bf16: 0 | fp4: 0 | warp size: 32 | shared memory: 49152 | int dot: 1 | matrix cores: none
    | model                          |       size |     params | backend    | ngl | dev          |            test |                  t/s |
    | ------------------------------ | ---------: | ---------: | ---------- | --: | ------------ | --------------: | -------------------: |
    | maple 20B TQ1_0 - 1.69 bpw ternary |   5.05 GiB |    20.21 B | Vulkan     |  -1 | none         |           pp512 |        174.98 ± 0.14 |
    | maple 20B TQ1_0 - 1.69 bpw ternary |   5.05 GiB |    20.21 B | Vulkan     |  -1 | none         |           tg128 |         23.52 ± 0.07 |

    build: 1537a0a8b (11379)
    ```

    </details>

    генерация — 23.5 ток/с, обработка промпта — 175 ток/с.

2. Если есть GPU — сравнить с gpt-oss-20b или Qwen3.5-27B

    —

3. Получить бесплатный API-ключ OpenRouter, сравнить качество с локальной моделью

    ```shell
    export LLM_API_KEY=<МОЙ_КЛЮЧ>
    ```

    ```shell
    curl -s http://127.0.0.1:8080/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{"messages": [{"role": "user", "content": "Сколько букв r в слове strawberry?"}]}' \
      | jq '{model, content: .choices[0].message.content}'
    ```
    <details><summary>Output</summary>

    ```json
    {
      "model": "models/maple-preview-TQ1_0-head-F16.gguf",
      "content": "В слове \"strawberry\" три буквы \"r\"."
    }
    ```

    </details>

    ```shell
    curl -s https://openrouter.ai/api/v1/chat/completions \
      -H "Authorization: Bearer $LLM_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"model": "nvidia/nemotron-3-super-120b-a12b:free", "messages": [{"role": "user", "content": "Сколько букв r в слове strawberry?"}]}' \
      | jq '{model, content: .choices[0].message.content}'
    ```
    <details><summary>Output</summary>

    ```json
    {
      "model": "nvidia/nemotron-3-super-120b-a12b:free",
      "content": "В слове «strawberry» три буквы «r».  \nПроверка по буквам: s-t-r-a-w-b-e-r-r-y → позиции 3, 8 и 9 заняты буквой «r».  \nПримечание: иногда из-за произношения кажется, что «r» всего две, но орфографически слово содержит три «r» (одна в части «straw» и две в части «berry»).  \n\nОтвет: **3**."
    }
    ```

    </details>

### Домашнее задание

1. Установить llama-cpp

    ```shell
    curl -LsSf https://llama.app/install.sh | sh
    ```
    <details><summary>Output</summary>

    ```
    Version: b11379
    Probing CUDA...
    Downloading cuda-probe...
    ./cuda-probe: error while loading shared libraries: libcuda.so.1: cannot open shared object file: No such file or directory
    Probing ROCm...
    Downloading rocm-probe...
    ./rocm-probe: error while loading shared libraries: libhipblas.so.3: cannot open shared object file: No such file or directory
    Probing Vulkan...
    Downloading vulkan-probe...
    Downloading featcode...
    Found: avx
    Found: f16c
    Found: fma
    Found: avx2
    Found: bmi2
    Found: avxvnni
    Downloading llama...
    Installation completed successfully

    Run the following command to start it:

      llama serve
    ```

    </details>

    ```shell
    llama download -mu https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf -m models/qwen2.5-3b-instruct-q4_k_m.gguf
    llama download -mu https://huggingface.co/unsloth/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf
    ```
    <details><summary>Output</summary>

    ```
    models/qwen2.5-3b-instruct-q4_k_m.gguf
    models/Llama-3.2-3B-Instruct-Q4_K_M.gguf
    ```

    </details>

    ```shell
    llama serve -m models/qwen2.5-3b-instruct-q4_k_m.gguf -dev none
    ```
    <details><summary>Output</summary>

    ```
    0.00.000.646 I srv  llama_server: initializing ...
    0.00.016.051 I cmn  common_param: common_params_print_info: verbosity = 3 (adjust with the `-lv N` CLI arg)
    0.00.016.203 W srv  llama_server: security: no API key is set and CORS allows all origins (see https://github.com/ggml-org/llama.cpp/pull/25655)
    0.00.017.520 I srv    load_model: loading model 'models/qwen2.5-3b-instruct-q4_k_m.gguf'
    0.00.279.016 W load: control-looking token: 128247 '</s>' was not control-type; this is probably a bug in the model. its type will be overridden
    0.01.231.131 I cmn          init: llama threadpool init, n_threads = 6
    0.02.035.650 I srv    load_model: initializing, n_slots = 4, n_ctx_slot = 32768, kv_unified = 'true'
    0.02.038.949 I srv  llama_server: model loaded
    0.02.038.954 I srv  llama_server: listening on http://127.0.0.1:8080
    0.02.038.955 W srv  llama_server: notice: server default port will be changed to :9931 in a future release (ref: https://github.com/ggml-org/llama.cpp/pull/26508)
    0.03.051.989 I slot get_availabl: id  3 | task -1 | selected slot by LRU, t_last = -1
    0.03.052.118 I slot launch_slot_: id  3 | task 0 | processing task, is_child = 0
    0.05.907.968 I slot print_timing: id  3 | task 0 | prompt eval time =     420.22 ms /    45 tokens (    9.34 ms per token,   107.09 tokens per second)
    0.05.907.970 I slot print_timing: id  3 | task 0 |        eval time =    2435.25 ms /    27 tokens (   93.66 ms per token,    10.68 tokens per second)
    0.05.907.971 I slot print_timing: id  3 | task 0 |       total time =    2855.48 ms /    72 tokens
    0.05.907.971 I slot print_timing: id  3 | task 0 |    graphs reused =         26
    0.05.907.983 I slot      release: id  3 | task 0 | stop processing: n_tokens = 71, truncated = 0
    ```

    </details>

    ```shell
    llama serve -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf -dev none
    ```
    <details><summary>Output</summary>

    ```
    0.00.000.777 I srv  llama_server: initializing ...
    0.00.015.184 I cmn  common_param: common_params_print_info: verbosity = 3 (adjust with the `-lv N` CLI arg)
    0.00.015.320 W srv  llama_server: security: no API key is set and CORS allows all origins (see https://github.com/ggml-org/llama.cpp/pull/25655)
    0.00.016.755 I srv    load_model: loading model 'models/Llama-3.2-3B-Instruct-Q4_K_M.gguf'
    0.05.476.473 I cmn          init: llama threadpool init, n_threads = 6
    0.10.572.299 I srv    load_model: initializing, n_slots = 4, n_ctx_slot = 131072, kv_unified = 'true'
    0.10.581.973 I srv  llama_server: model loaded
    0.10.581.975 I srv  llama_server: listening on http://127.0.0.1:8080
    0.10.581.976 W srv  llama_server: notice: server default port will be changed to :9931 in a future release (ref: https://github.com/ggml-org/llama.cpp/pull/26508)
    0.11.119.690 I slot get_availabl: id  3 | task -1 | selected slot by LRU, t_last = -1
    0.11.119.758 I slot launch_slot_: id  3 | task 0 | processing task, is_child = 0
    0.13.857.156 I slot print_timing: id  3 | task 0 | prompt eval time =     422.25 ms /    50 tokens (    8.45 ms per token,   118.41 tokens per second)
    0.13.857.159 I slot print_timing: id  3 | task 0 |        eval time =    2314.54 ms /    25 tokens (   96.44 ms per token,    10.37 tokens per second)
    0.13.860.162 I slot print_timing: id  3 | task 0 |       total time =    2736.80 ms /    75 tokens
    0.13.860.164 I slot print_timing: id  3 | task 0 |    graphs reused =         24
    0.13.860.357 I slot      release: id  3 | task 0 | stop processing: n_tokens = 74, truncated = 0
    ```

    </details>

    ```shell
    curl -s http://127.0.0.1:8080/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{"messages": [{"role": "user", "content": "Привет! Кто ты? Ответь одним предложением."}]}' \
      | jq '{model, content: .choices[0].message.content, tokens_per_second: .timings.predicted_per_second}'
    ```
    <details><summary>Output</summary>

    ```json
    {
      "model": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
      "content": "Я Qwen, созданный Alibaba Cloud, чтобы быть полезным и информативным ассистентом.",
      "tokens_per_second": 10.676508765208377
    }
    {
      "model": "models/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
      "content": "Я - интеллектуальный assistant, способный предоставить информацию и ответы на tua вопросы.",
      "tokens_per_second": 10.369231035108488
    }
    ```

    </details>

2. Подключение к OpenRouter

    Ключ и вызов модели из OpenRouter — в п. 3 раздела [Развёртывание LLM](#развёртывание-llm--домашнее-задание).

3. Консольный чат

    Исходники — [`hw01.py`](hw01.py).

    ```shell
    poetry install
    poetry run python hw01.py --prompt chat
    ```
    <details><summary>Output</summary>

    ```
    model: models/qwen2.5-3b-instruct-q4_k_m.gguf
    > Какой шрифт нужен для основного текста ВКР?
    Основной текст ВКР должен быть напечатан на основе шрифта Times New Roman размером 12 пунктов.
    > А межстрочный интервал?
    Межстрочный интервал должен быть установлен на 1.5 строке.
    > /exit
    ```

    </details>

4. Ассистент с вызовом функций (tools)

    Исходники — [`hw01.py`](hw01.py).

    ```shell
    poetry run python hw01.py --prompt v4
    ```
    <details><summary>Output</summary>

    ```
    model: models/qwen2.5-3b-instruct-q4_k_m.gguf
    > Проверь поля страницы.
    $function$get_thesis(margins)$function$
    $function$get_requirements(margins)$function$
    -> {"left_mm": 25, "right_mm": 10, "top_mm": 20, "bottom_mm": 20}
    $function$get_requirements(margins)$function$
    -> [{"text": "Текст ВКР следует печатать, соблюдая следующие размеры полей: левое - 30 мм, правое - 10 мм, верхнее и нижнее - 20 мм.", "source": "Требования к ВКР ИИТ 2019, п. 5.7.2"}]
    - левое поле: в работе 25 мм, требуется 30 мм — нарушение
    - правое поле: в работе 10 мм, требуется 10 мм — соответствует
    - верхнее поле: в работе 20 мм, требуется 20 мм — соответствует
    - нижнее поле: в работе 20 мм, требуется 20 мм — соответствует
    > /exit
    ```

    </details>

5. Прогон на 2 LLM + логи

    Вопросы, одинаковые для обеих моделей:

    1. Проверь поля страницы.
    2. Какие шрифт и интервал в основном тексте? Всё ли по требованиям?
    3. Все ли обязательные разделы есть в работе?
    4. Правильно ли оформлены заголовки?
    5. Проверь список литературы.
    6. Правильно ли выбраны размер шрифта и абзацный отступ?
    7. Есть ли в работе заключение?
    8. Хватает ли источников в списке литературы?
    9. Правильные ли верхнее и нижнее поля?
    10. Есть ли заголовки с точкой в конце?

    ```shell
    poetry run python hw01.py --prompt v1
    ```

    Логи: [Qwen2.5-3B](logs/hw01/qwen2.5-3b-instruct-q4_k_m.v1.log), [Llama-3.2-3B](logs/hw01/Llama-3.2-3B-Instruct-Q4_K_M.v1.log).

    Qwen ни разу не вызвала `get_thesis`: пересказывает требования, а работу не проверяет. Llama не вызвала ни одной функции: отвечает выдуманными требованиями (поля 2,5 см, шрифт 12 пт) и мешает русский с английским.

6. Prompt engineering до 4B

    Модель — Qwen2.5-3B, вопросы из п. 5. Промпты — `PROMPT_V1`–`PROMPT_V4` в [`hw01.py`](hw01.py).

    ```shell
    poetry run python hw01.py --prompt v2
    poetry run python hw01.py --prompt v3
    poetry run python hw01.py --prompt v4
    ```

    Логи: [v2](logs/hw01/qwen2.5-3b-instruct-q4_k_m.v2.log), [v3](logs/hw01/qwen2.5-3b-instruct-q4_k_m.v3.log), [v4](logs/hw01/qwen2.5-3b-instruct-q4_k_m.v4.log).

    | Промпт | Что изменено | Результат |
    |---|---|---|
    | v1 | роль, задача, функции, формат вызова | вызывает только `get_requirements` и пересказывает требования |
    | v2 | шаги проверки, правила, пример диалога | вызывает одну функцию из двух и выдумывает вывод: «заключение есть», поля «соответствуют» |
    | v3 | запрет писать результаты функций, пример описанием, ответ построчно | оба вызова — только на вопрос из примера («Проверь поля страницы.») |
    | v4 | шаблон из трёх ответов с вызовами, темы с русскими ключевыми словами, в строке сначала значение из работы, вердикт «нет данных» | оба вызова с нужной темой во всех 30 вопросах трёх прогонов |

    На v4 Qwen находит нарушения полей и интервала, нехватку источников и отсутствие «Заключения», если спросить о нём прямо. На общие вопросы про разделы и заголовки отвечает, что всё верно, а точку в конце «1.1 Обзор существующих решений.» не замечает даже на прямой вопрос. «1,25 см» из требований часто копирует как «1 см», в одном прогоне из трёх это дало ложные нарушения. В списке литературы называет отступ, которого в данных нет.

## Задание 02

### Чат-агент на LangChain с памятью в файле

1. Собрать чат на LangChain (цепочка / chain)

    Агент из [`hw02.py`](hw02.py) на Qwen2.5-3B читает титульный лист, спрашивает, начинать ли анализ, и проверяет ВКР по требованиям ИИТ ЧелГУ из задания 01.

    ```shell
    llama serve -m models/qwen2.5-3b-instruct-q4_k_m.gguf -dev none
    poetry install
    poetry run python hw02.py data/vkr.docx --user ivanov
    ```
    <details><summary>Output</summary>

    ```
    ЧелГУ, Институт информационных технологий. Проверю по документам: «Требования к ВКР ИИТ 2019», «Оформление ВКР ИИТ 2025». Начать анализ?
    > да
    Нашёл нарушения:
    1. Левое поле: 25 мм, нужно 30 мм (Требования к ВКР ИИТ 2019, п. 5.7.2)
    2. Междустрочный интервал: 1, нужно 1,5; абзацев 7, например «Учёт учебной нагрузки преподавателей на …» (Требования к ВКР ИИТ 2019, п. 5.7.1)
    3. Нет раздела «Заключение» (Требования к ВКР ИИТ 2019, п. 5.1)
    4. Точка в конце заголовка «1.1 Обзор существующих решений.» (Требования к ВКР ИИТ 2019, п. 5.7.3)
    5. Источников: 4, нужно не менее 20 (Оформление ВКР ИИТ 2025, слайд 14)
    6. Иностранный источник перед русскими: «2. Smith, J. Document Processing Pipelin…» (Оформление ВКР ИИТ 2025, слайд 14)
    7. Нарушен алфавитный порядок: «1. Петров, А. В. Проектирование информац…» перед «3. Алексеев, Б. Г. Обработка текстов на …» (Оформление ВКР ИИТ 2025, слайд 14)
    Не проверял: Список использованной литературы оформляется в соответствии с ГОСТ 7.1-2003 (Требования к ВКР ИИТ 2019, п. 5.7.7).
    > /exit
    ```

    </details>

2. Агент извлекает и сохраняет ключевые факты о пользователе

    Вуз, институт и кафедру извлекает отдельный вызов модели со structured output. Значения, которых нет в тексте, отбрасываются, а недостающее агент спрашивает.

3. Память — не история чата, а набор фактов

    В файл пишутся только факты.

4. Факты пишутся в файл и читаются при старте

    [`memory.json`](memory.json) хранит факты о каждом пользователе (`--user`).

    <details><summary>memory.json</summary>

    ```json
    {
      "ivanov": {
        "facts": {
          "university": "ЧелГУ",
          "institute": "Институт информационных технологий",
          "department": "Кафедра информационных технологий и экономической информатики"
        }
      }
    }
    ```

    </details>

5. Перезапуск: агент помнит факты

    После перезапуска факты берутся из памяти. Без файла агент просит путь.

    ```shell
    poetry run python hw02.py data/vkr.docx --user ivanov
    ```
    <details><summary>Output</summary>

    ```
    ЧелГУ, Институт информационных технологий. Проверю по документам: «Требования к ВКР ИИТ 2019», «Оформление ВКР ИИТ 2025». Начать анализ?
    > /exit
    ```

    </details>

    ```shell
    poetry run python hw02.py --user ivanov
    ```
    <details><summary>Output</summary>

    ```
    Укажите путь к файлу ВКР в формате .docx.
    > data/vkr.docx
    ЧелГУ, Институт информационных технологий. Проверю по документам: «Требования к ВКР ИИТ 2019», «Оформление ВКР ИИТ 2025». Начать анализ?
    > /exit
    ```

    </details>

6. Служебная информация — через собственную ячейку цепочки

    Шаги `log_step` пишут в [`logs/hw02/`](logs/hw02/) сообщения, которые уходят в модель, её ответы и сохранённые факты; в чат идут только ответы.

    <details><summary>Output</summary>

    ```
    2026-10-12 16:56:51 INFO opened vkr.docx: 40 blocks
    2026-10-12 16:56:51 INFO prompt: [system] Ты извлекаешь факты о выпускной работе студента из текста: её титульного листа… | [human] Министерство науки и высшего образования Российской Федерации Федеральное… | [ai] {"university":"Национальный исследовательский Томский государственный… | [human] «Новосибирский государственный технический университет» Кафедра вычислительной… | [ai] {"university":"Новосибирский государственный технический… | [human] Проверь, пожалуйста, мою ВКР. | [ai] {"university":null,"institute":null,"department":null} | [human] УрФУ, ИРИТ-РтФ. | [ai] {"university":"УрФУ","institute":"ИРИТ-РтФ","department":null} | [human] МИНОБРНАУКИ РОССИИ Федеральное государственное бюджетное образовательное…
    2026-10-12 16:56:57 INFO extracted: {"university":"ЧелГУ","institute":"Институт информационных технологий","department":"Кафедра информационных технологий и экономической информатики"}
    2026-10-12 16:56:57 INFO kept: {"university":"ЧелГУ","institute":"Институт информационных технологий","department":"Кафедра информационных технологий и экономической информатики"}
    2026-10-12 16:56:57 INFO facts: {"university":"ЧелГУ","institute":"Институт информационных технологий","department":"Кафедра информационных технологий и экономической информатики"}
    2026-10-12 16:56:57 INFO user: да
    2026-10-12 16:56:57 INFO consent: {"agrees":true}
    2026-10-12 16:56:57 INFO Margins problems: 1
    2026-10-12 16:56:57 INFO BodyText problems: 1
    2026-10-12 16:56:57 INFO Structure problems: 1
    2026-10-12 16:56:57 INFO Headings problems: 1
    2026-10-12 16:56:57 INFO Bibliography problems: 3
    ```

    ```
    2026-10-12 16:56:59 INFO session started, file: data/vkr.docx
    2026-10-12 16:56:59 INFO opened vkr.docx: 40 blocks
    2026-10-12 16:56:59 INFO assistant: ЧелГУ, Институт информационных технологий. Проверю по документам: «Требования к ВКР ИИТ 2019», «Оформление ВКР ИИТ 2025». Начать анализ?
    ```

    </details>
