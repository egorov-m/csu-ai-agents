# csu-ai-agents

## Содержание

- [Задание 01](#задание-01)
  - [Развёртывание LLM — Домашнее задание](#развёртывание-llm--домашнее-задание)
  - [Домашнее задание](#домашнее-задание)

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
