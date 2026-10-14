"""Mac-only local entrypoint; original Windows scripts and config stay unchanged."""
import argparse
import os
from pathlib import Path
import runpy
import secrets
import sys

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'backend'
LOCAL = ROOT / '.local-mac'


def main():
    parser = argparse.ArgumentParser(description='Mac 独立测试环境')
    parser.add_argument('action', choices=['prepare', 'web', 'worker', 'models'])
    parser.add_argument('--once', action='store_true', help='worker 仅消费一轮')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('此入口仅用于 Mac；Windows 继续使用原启动方式')
    if args.once and args.action != 'worker':
        parser.error('--once 仅用于 worker')
    if args.action in ('web', 'worker') and not (LOCAL / 'app.db').exists():
        parser.error('请先运行 python mac-local.py prepare')
    LOCAL.mkdir(exist_ok=True)
    sys.path.insert(0, str(BACKEND))
    os.chdir(LOCAL)
    os.environ['DATABASE_URL'] = 'sqlite:///' + (LOCAL / 'app.db').as_posix()
    os.environ['OCR_MODEL_ROOT'] = str(LOCAL / 'ocr-models')
    os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
    sys.dont_write_bytecode = True
    if args.action == 'models':
        runpy.run_path(str(BACKEND / 'tools/setup_certificate_models.py'), run_name='__main__')
        return

    # Override the imported class before Flask/extensions initialize; no file edits.
    from config import Config
    folders = {
        'UPLOAD_FOLDER': LOCAL / 'uploads',
        'AVATAR_FOLDER': LOCAL / 'uploads/avatars',
        'FILE_FOLDER': LOCAL / 'uploads/files',
        'GRADUATE_FILES_FOLDER': LOCAL / 'uploads/graduate-files',
        'SESSION_FILE_DIR': LOCAL / 'sessions',
        'AUTOMATION_UPLOAD_FOLDER': LOCAL / 'private-materials',
        'CERTIFICATE_STORAGE_FOLDER': LOCAL / 'private-certificates',
        'MATERIAL_STORAGE_FOLDER': LOCAL / 'private-evidence',
    }
    for key, path in folders.items():
        path.mkdir(parents=True, exist_ok=True)
        setattr(Config, key, str(path))
    secret = LOCAL / 'session-secret'
    try:
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w') as output:
            output.write(secrets.token_hex(32))
    Config.SECRET_KEY = secret.read_text().strip()
    Config.SESSION_COOKIE_NAME = 'gradpush_mac_session'
    if args.action == 'prepare':
        from tools import prepare_local
        # Reuse known legacy schema preparation on our own copy, never its default DB.
        prepare_local.LOCAL = LOCAL / 'app.db'
        prepare_local.main()
    elif args.action == 'web':
        from app import app
        app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
    else:
        import recognition_worker
        sys.argv = ['recognition_worker.py'] + (['--once'] if args.once else [])
        recognition_worker.main()


if __name__ == '__main__':
    main()
