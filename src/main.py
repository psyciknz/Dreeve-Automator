"""Main module of the program - entry point."""
import logging
import time
import timeit

import activity
import dreeve_api
import configure
import generate
from const import LOG_FILE


def main() -> None:
    """Main procedure of the program."""
    logging.basicConfig(
        handlers=(logging.FileHandler(LOG_FILE), logging.StreamHandler()),
        encoding="utf8", level=logging.INFO,
        format= "%(asctime)s: %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    try:
        config = configure.get_config()
    except Exception as e:
        logging.error(f"Config file error: {e}")
        return
    session = dreeve_api.create_session(
        config.dreeve_url, config.dreeve_api_key)
    while True:
        start = timeit.default_timer()
        activities = activity.get_activities(session)
        for activity_ in activities:
            if not activity.can_process_activity(activity_):
                continue
            try:
                title, description = (
                    generate.generate_title_and_description(activity_, config))
            except RuntimeError:
                continue
            activity.update_activity(
                activity_.id, title, description, session)
        if activities:
            logging.info("New activities processed and any renames applied.")
        else:
            logging.info("No new activities detected.")
        stop = timeit.default_timer()
        time.sleep(max(0, config.refresh_minutes * 60 - (stop - start)))
        

if __name__ == "__main__":
    main()
