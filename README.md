# Remember releases assets of projects

Remember projects releases assets and compute theirs SHA256 checksums.

Useful for updating automatic installation tool on newer releases of projects.
Projects states are stored in JSON and saved in current repository.

Only Github projects are supported.

## Installation

This is local executable only. Create a local environment for running python
program.

```sh
py -m venv .venv
# All Unix
. .venv/bin/activate
# Windows cmd.exe
.\.venv\Scripts\activate.bat
# Windows Powershell
.\.venv\Scripts\activate.ps1
```

Install dependencies.

```sh
pip install -r requirements.txt
```

## Run program

From created virtual environment, run module as main program.

```py
# All Unix
.venv/bin/python -m ghrel gh-releases.toml
# Windows
.venv\Scrips\python -m ghrel gh-releases.toml
```
