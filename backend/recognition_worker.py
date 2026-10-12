"""启动：python recognition_worker.py；单批处理：--once。"""
import argparse
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    from app import app
    from extensions import db
    from services.recognition.provider import PaddleProvider
    from services.recognition.worker import run_one
    provider = PaddleProvider()
    with app.app_context():
        while True:
            try:
                processed = run_one(app, provider)
            except Exception:
                db.session.rollback()
                app.logger.exception("识别工作进程异常，任务租约到期后可恢复")
                if args.once:
                    raise
                processed = False
            if args.once:
                break
            if not processed:
                time.sleep(2)
            db.session.remove()


if __name__ == "__main__":
    main()
