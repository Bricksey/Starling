# Starling

*Starling* is a simple, modular Discord bot with automatic cog loading.

## Configuration
Environment variables or arguments can currently be used to configure the bot.

| Argument             | Environment Variable | Description                                                      |
|----------------------|----------------------|------------------------------------------------------------------|
| `-t`<br/>`--token`   | `TOKEN`              | Set the bot's authentication token. Required for running.        |
| `-p`<br/>`--prefix`  | `PREFIX`             | Set the prefix used to invoke bot commands. <br/>Defaults to `!` |
| `-v`<br/>`--verbose` | None                 | Enable debug logging                                             |

The bundled cogs are configured with commands and will write their configuration to `./config/`

## Bundled cogs

| Name    | Description                                                              |
|---------|--------------------------------------------------------------------------|
| Base    | Core commands and functionality                                          |
| Mumble  | Track the user count in a given mumble server with notification support. |
| ping    | Responds to the `ping` command, shows basic cog functionality.           |
| Profile | Edit the bot's Discord profile.                                          |

## Running Locally
This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

Run the bot using `uv run main.py`, ensuring your token is set.<br>
Once the bot is running, run `help` for more information on the bundled cogs.

## Running with Docker
An example [compose file](compose.yml) is included, ensure the token is set and the `config` directory is created before running.



