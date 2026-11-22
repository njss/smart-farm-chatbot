# 💬 Shamba Smart: farmer advisory chatbot

Part of the **Smart Farm workshop kit** for the Africa-UniNet project *Developing AI Competency for Sustainability in Ethiopia and Tanzania* (smart agriculture).

A web chatbot that advises a farmer **from live sensor data**, in **English or Swahili**:

- The page subscribes to the farm's sensors over MQTT (see [TOPICS.md](TOPICS.md)).
- Each question is sent to `/api/chat` together with the latest reading.
- A **rule-based advisor** (`api/_advisor.py`) checks soil moisture, heat, humidity and rain against crop thresholds.
- If an AI key is configured, **Claude** (through the Vercel AI Gateway) writes the answer, grounded in those rule findings. Without a key, the rules answer directly, so the app works offline and for free.

Also included: manual input when no sensors are connected, a pump on/off button, and quick-question buttons.

## Run locally (Python only)

```bash
python dev_server.py           # http://localhost:8000
```

Start the simulator from `smart-farm-sensors` in another terminal (`python simulator.py`) and you will see live values. To use Claude locally:

```bash
export AI_GATEWAY_API_KEY=...  # Vercel dashboard → AI Gateway → API keys
python dev_server.py
```

## Deploy to Vercel

1. Import this repo in Vercel (no framework preset needed: static files + a Python function in `api/`).
2. Optional: enable **AI Gateway** for the project. On Vercel the function authenticates automatically with the project's OIDC token, or you can set `AI_GATEWAY_API_KEY`.
3. Optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `CHAT_MODEL` | `anthropic/claude-haiku-5.5` | any model id from the AI Gateway catalogue |
| `CHAT_DISABLE_LLM` | unset | set to `1` to force rules-only mode |
| `AI_GATEWAY_API_KEY` | unset | explicit key instead of OIDC |

Change the broker or the twin link in [`config.js`](config.js). URL parameters: `?farm=team-3&crop=tomato&lang=sw`.

## How the advice is produced

```
sensor reading ──► _advisor.assess() ──► findings (action / watch / ok, EN + SW)
                                            │
                       no AI key ◄──────────┼──────────► AI key
                 rules_reply(): topic-matched       _llm.ask(): Claude answers the
                 findings in the chosen language    question, grounded in the reading
                                                    and the findings
```

The system prompt (in `api/_llm.py`) tells the model to rely only on the provided data, keep answers short and simple, never recommend specific pesticides, and refer farmers to the extension officer when data cannot answer.

> ⚠️ Crop thresholds in `CROPS` are indicative starting points, not certified agronomic advice. The Swahili text should be reviewed by native speakers and local agronomists; improving it is a workshop task.

## 🧑🏾‍🎓 Student tasks

1. **Check the rules with experts.** Interview an agronomist or extension officer. Correct the thresholds in `CROPS` for your region and crops, and note the source in a comment.
2. **Add a crop or a rule.** For example: frost warning for potatoes, or "do not spray before rain".
3. **Improve the language.** Review the Swahili findings with native speakers. Add a third language (for example Amharic for the Ethiopian partners).
4. **Compare rules vs. LLM.** Ask the same 10 questions with and without `CHAT_DISABLE_LLM=1`. Which answers are more useful, more accurate, more risky? Write down why.
5. **Design for the farmer.** Many farmers use basic phones. Sketch how the same advice could reach them by SMS, WhatsApp or voice.

## Tests

```bash
pip install pytest && python -m pytest
```

## License

MIT. See [LICENSE](LICENSE). Bundles [MQTT.js](https://github.com/mqttjs/MQTT.js) (MIT) in `vendor/`.
