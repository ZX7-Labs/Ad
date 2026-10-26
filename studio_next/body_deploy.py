"""Set up the independent ZX7 BODY as a durable *local* Linux user service.

The agent is not a chatbot-dependent background job. It runs trusted local
programs with persistent disk and a loopback-only authenticated API.
No paid provider, no automatic systemctl enable, no model/style instructions.

The secret lives outside the film project vault and git checkout. Never copy
the token into shareable original-film archives, model prompts or user output.
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path


def _safe_unit_path(path):
    path=Path(path).expanduser().resolve()
    if "\n" in str(path) or "\r" in str(path) or not path.is_absolute():
        raise ValueError("Executable service path contains unsafe unit characters")
    return path


def _systemd_quote(path):
    # Unit arguments are not shell commands. Quote whitespace/semicolons
    # with native systemd double-quoted arguments; no arbitrary user's
    # shell expression or model-authored script is evaluated.
    value=str(_safe_unit_path(path))
    if '"' in value or "\\" in value or "%" in value:
        raise ValueError("Unsafe original studio path for systemd unit")
    return '"'+value+'"'


def configure_independent_studio(workspace,*,config_dir=None,unit_dir=None,
                                code_root=None,python=None):
    if sys.platform!="linux":
        raise RuntimeError("Local durable user-service installer currently supports Linux")
    home=_safe_unit_path(workspace)
    code=_safe_unit_path(code_root or Path(__file__).resolve().parent.parent)
    config=_safe_unit_path(config_dir or (Path.home()/".config"/"zx7-studio"))
    units=_safe_unit_path(unit_dir or (Path.home()/".config"/"systemd"/"user"))
    python=_safe_unit_path(python or sys.executable)
    if home==code or home.is_relative_to(code) or code.is_relative_to(home):
        raise ValueError("Persistent user films must not be stored inside a code checkout")
    if config==home or config.is_relative_to(home):
        raise ValueError("Authentication secrets must not enter shareable film backups")
    if config==code or config.is_relative_to(code):
        raise ValueError("Never commit a local creative owner token into source control")
    if units.is_relative_to(home) or units.is_relative_to(code):
        raise ValueError("User service unit cannot reside inside films or source checkout")
    if not python.is_file() or not (code/"studio_next"/"body_service.py").is_file():
        raise ValueError("Cannot install nonexistent studio executable source")
    home.mkdir(parents=True,exist_ok=True)
    config.mkdir(mode=0o700,parents=True,exist_ok=True)
    units.mkdir(parents=True,exist_ok=True)
    env=config/"body.env"
    if not env.exists():
        token=secrets.token_urlsafe(48)
        with os.fdopen(os.open(env,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"w") as out:
            out.write("ZX7_BODY_API_TOKEN="+token+"\n")
            out.flush()
            os.fsync(out.fileno())
    if env.is_symlink() or not env.is_file():
        raise ValueError("Refuse inherited/symlinked service authentication secret")
    permissions=stat.S_IMODE(env.stat().st_mode)
    if permissions & 0o077:
        raise ValueError("Private studio token unexpectedly readable by other users")
    line=env.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"ZX7_BODY_API_TOKEN=[A-Za-z0-9_-]{32,128}",line):
        raise ValueError("Local token storage is not a valid private owner secret")
    program=_systemd_quote(python)
    source_root=_systemd_quote(code)
    space=_systemd_quote(home)
    token_file=_systemd_quote(env)
    unit=units/"zx7-studio-body.service"
    content=(
       "[Unit]\n"
       "Description=ZX7 autonomous creative BODY (localhost only)\n"
       "After=network.target\n\n"
       "[Service]\n"
       "Type=simple\n"
       f"WorkingDirectory={source_root}\n"
       f"EnvironmentFile={token_file}\n"
       f"ExecStart={program} -m studio_next.body_service --workspace-root {space} --port 8765 --workers 1\n"
       "Restart=on-failure\n"
       "RestartSec=5\n"
       "UMask=0077\n"
       "NoNewPrivileges=true\n"
       "PrivateTmp=true\n\n"
       "[Install]\n"
       "WantedBy=default.target\n"
    )
    if unit.is_symlink():
        raise ValueError("Original local systemd service unit cannot be a symlink")
    if unit.exists() and not unit.is_file():
        raise FileExistsError("Existing original service unit is not a regular file")
    if unit.is_file():
        if unit.read_text(encoding="utf-8")!=content:
            raise FileExistsError("Existing production service unit changed; inspect before replacing")
    else:
        # A plain write_text() follows broken symlinks and can truncate other
        # artists' host files, including an unrelated installation. A unit
        # is committed only as a brand-new owner-specific pathname.
        try:
            with unit.open("x",encoding="utf-8") as created:
                created.write(content)
                created.flush()
                os.fsync(created.fileno())
        except FileExistsError:
            if (unit.is_symlink() or not unit.is_file() or
                    unit.read_text(encoding="utf-8")!=content):
                raise FileExistsError(
                    "Competing host operator installed a different or linked service")
        folder_fd=os.open(units,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(folder_fd)
        finally:os.close(folder_fd)
    return {"configured":True,"service_unit":str(unit),
            "persistent_workspace_root":str(home),
            "operator_secret_path":str(env),
            "secret_excluded_from_filmmaking_workspace":True,
            "enabled_automatically":False,
            "host_network_interface":"127.0.0.1",
            "commands_to_activate":["systemctl --user daemon-reload",
                                    "systemctl --user enable --now zx7-studio-body.service"],
            "password_or_api_token":None}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace-root",type=Path,default=Path.home()/".local"/"share"/"zx7-studio")
    p.add_argument("--config",type=Path)
    p.add_argument("--units",type=Path)
    p.add_argument("--enable",action="store_true",
                   help="Explicit permission to enable/start original studio Linux user service")
    args=p.parse_args(argv)
    result=configure_independent_studio(args.workspace_root,config_dir=args.config,
                                        unit_dir=args.units)
    if args.enable:
        subprocess.run(["systemctl","--user","daemon-reload"],check=True,timeout=30)
        subprocess.run(["systemctl","--user","enable","--now",
                        "zx7-studio-body.service"],check=True,timeout=60)
        result["enabled_automatically"]=True
    import json
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
