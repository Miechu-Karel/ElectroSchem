# AI assistant and command safety

Applies to ElectroSchem 1.3.0.

## Current interface

The visible assistant is for questions and explanations. Circuit drawing,
proposal editing, and the editor command terminal are hidden in this release;
their implementation is retained for possible future use but is not exposed
through the normal interface. The AI button is hidden when the provider is set
to **None**.

## Providers

Choose Gemini, OpenAI, Local AI, or None in Settings. Cloud providers need
their own API key and may charge separately from a ChatGPT subscription. The
OpenAI model ID can be changed in AI settings. Local AI needs an already-running
compatible server and a model loaded there; ElectroSchem does not download or
start models. Settings includes a local-AI setup guide and accepts an optional
local API token.

## Privacy and costs

Requests are sent only after consent. Remembered consent is stored per provider
and can be revoked in Settings. API keys are protected locally with Windows
DPAPI and are not included in project files. Cloud requests go to the selected
provider and can incur API charges. Local requests go to the configured server;
its own network and privacy settings remain under the user's control.

The assistant does not run shell commands, execute model-generated Python, or
access arbitrary files. Treat explanations as guidance and verify important
electrical designs independently.
