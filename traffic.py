"""
Acquired and modified from https://github.com/sangonzal/repository-traffic-action

This script is supposed to run on Github Actions.

Prerequisites
=============
Set a personal access token with `repo` permissions as `TRAFFIC_ACTION_TOKEN` in environment variables.

Usage
=====
Setup a Github Action workflow to run this script at a scheduled interval.
"""
from abc import ABC, abstractmethod
import csv
from datetime import date, datetime
from enum import IntEnum
from typing import List, Tuple, Dict, Optional, Any, Iterable, Generator, Type
import os

from github import Github, Repository


TODAY_UTC = datetime.utcnow()


class DataController(ABC):
    DATE_FORMAT = "%Y-%m-%d"

    CSV_HEADER_ENUM_CLASS: Type[IntEnum]

    @abstractmethod
    def load_or_update_from_gh_repo(self, repo: Repository):
        raise NotImplementedError()

    @abstractmethod
    def load_or_update_from_data(self, data_path: Optional[str]):
        raise NotImplementedError()

    @abstractmethod
    def get_sorted_data_generator(self) -> Generator[List[Tuple[Any]], None, None]:
        raise NotImplementedError()

    def export_to_csv(self, export_path: str):
        with open(export_path, "a+", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(self.CSV_HEADER_ENUM_CLASS.as_header())
            csv_writer.writerows(self.get_sorted_data_generator())


class DataHeaderMixin:
    @classmethod
    def as_header(cls: Iterable[Any]) -> List[str]:
        return [item.name.replace("_", " ").title() for item in cls]


class TrafficViewHeader(DataHeaderMixin, IntEnum):
    DATE = 0
    VIEWS = 1
    UNIQUE_VISITORS = 2


class TrafficViewData(DataController):
    CSV_HEADER_ENUM_CLASS: Type[IntEnum] = TrafficViewHeader

    def __init__(self):
        self._data: Dict[date, Tuple[int, int]] = {}

    def load_or_update_from_gh_repo(self, repo: Repository):
        for data in repo.get_views_traffic()["views"]:
            self._data[data.timestamp] = (data.count, data.uniques)

    def load_or_update_from_data(self, data_path: Optional[str]):
        # Skip loading the data if path is `None`
        if not data_path:
            return

        with open(data_path, newline="", encoding="utf-8") as csv_file:
            csv_reader = csv.reader(csv_file)
            
            next(csv_reader)  # Dump header

            for row in csv_reader:
                data_date = datetime.strptime(row[TrafficViewHeader.DATE], self.DATE_FORMAT)
                data_views = int(row[TrafficViewHeader.VIEWS])
                data_visitors = int(row[TrafficViewHeader.UNIQUE_VISITORS])

                self._data[data_date] = (data_views, data_visitors)

    def get_sorted_data_generator(self) -> Generator[List[Tuple[date, int, int]], None, None]:
        for rec_date, stats in sorted(self._data.items(), key=lambda item: item[0]):
            yield rec_date.strftime(self.DATE_FORMAT), *stats


class TopReferrerHeader(DataHeaderMixin, IntEnum):
    DATE = 0
    COUNT = 1
    REFERRER = 2
    UNIQUE_VISITORS = 3


class TopReferrerData(DataController):
    CSV_HEADER_ENUM_CLASS: Type[IntEnum] = TopReferrerHeader

    def __init__(self):
        self._data: List[Tuple[datetime, int, str, int]] = []

    def load_or_update_from_gh_repo(self, repo: Repository):
        for data in repo.get_top_referrers():
            self._data.append((TODAY_UTC, data.count, data.referrer, data.uniques))

    def load_or_update_from_data(self, data_path: Optional[str]):
        # Skip loading the data if path is `None`
        if not data_path:
            return

        with open(data_path, newline="", encoding="utf-8") as csv_file:
            csv_reader = csv.reader(csv_file)
            
            next(csv_reader)  # Dump header

            for row in csv_reader:
                data_date = datetime.strptime(row[TopReferrerHeader.DATE], self.DATE_FORMAT)
                data_count = int(row[TopReferrerHeader.COUNT])
                data_referrer = row[TopReferrerHeader.REFERRER]
                data_visitors = int(row[TopReferrerHeader.UNIQUE_VISITORS])

                self._data.append((data_date, data_count, data_referrer, data_visitors))

    def get_sorted_data_generator(self) -> Generator[List[Tuple[str, int, str, int]], None, None]:
        for entry in sorted(self._data, key=lambda item: (item[0], -item[1])):
            yield entry[0].strftime('%Y-%m-%d'), *entry[1:]


class TopPathHeader(DataHeaderMixin, IntEnum):
    DATE = 0
    COUNT = 1
    PATH = 2
    TITLE = 3
    UNIQUE_VISITORS = 4


class TopPathData(DataController):
    CSV_HEADER_ENUM_CLASS: Type[IntEnum] = TopPathHeader

    def __init__(self):
        self._data: List[Tuple[datetime, int, str, str, int]] = []

    def load_or_update_from_gh_repo(self, repo: Repository):
        for data in repo.get_top_paths():
            self._data.append((TODAY_UTC, data.count, data.path, data.title, data.uniques))

    def load_or_update_from_data(self, data_path: Optional[str]):
        # Skip loading the data if path is `None`
        if not data_path:
            return

        with open(data_path, newline="", encoding="utf-8") as csv_file:
            csv_reader = csv.reader(csv_file)
            
            next(csv_reader)  # Dump header

            for row in csv_reader:
                data_date = datetime.strptime(row[TopPathHeader.DATE], self.DATE_FORMAT)
                data_count = int(row[TopPathHeader.COUNT])
                data_path = row[TopPathHeader.PATH]
                data_title = row[TopPathHeader.TITLE]
                data_visitors = int(row[TopPathHeader.UNIQUE_VISITORS])

                self._data.append((data_date, data_count, data_path, data_title, data_visitors))

    def get_sorted_data_generator(self) -> Generator[List[Tuple[datetime, int, str, str, int]], None, None]:
        for entry in sorted(self._data, key=lambda item: (item[0], -item[1])):
            yield entry[0].strftime('%Y-%m-%d'), *entry[1:]


class ReportGenerator:
    @staticmethod
    def get_repo() -> Repository:
        # Check repo setup
        if "GITHUB_REPOSITORY" not in os.environ:
            print("`GITHUB_REPOSITORY` not defined in the enviroment variables. "
                  "Make sure that the script is ran on Gihub Actions.")
            exit()
        gh_repo_name = os.environ["GITHUB_REPOSITORY"]

        # Initiate Github Instance
        if "TRAFFIC_ACTION_TOKEN" not in os.environ:
            print("`TRAFFIC_ACTION_TOKEN` not defined in the enviroment variables. "
                  "This is a Github personal access token with `repo` permissions.")
            exit()
        github = Github(os.environ["TRAFFIC_ACTION_TOKEN"])

        # Get repo
        return github.get_repo(gh_repo_name)

    @staticmethod
    def get_workspace_path(sub_path: str) -> str:
        # Check repo setup
        if "GITHUB_WORKSPACE" not in os.environ:
            print("`GITHUB_WORKSPACE` not defined in the enviroment variables. "
                  "Make sure that the script is ran on Gihub Actions.")
            exit()
        path_workspace = os.path.join(os.environ["GITHUB_WORKSPACE"], sub_path)

        # Create directory if not exists
        if not os.path.exists(path_workspace):
            os.makedirs(path_workspace)

        return path_workspace

    @staticmethod
    def get_latest_report_path(data_dir: str) -> Optional[str]:
        if not os.path.exists(data_dir):
            return None

        data_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]

        if not data_files:
            return None

        return os.path.join(data_dir, max(data_files))

    def __init__(self):
        self._repo: Repository = self.get_repo()

    def generate_report(self, workspace_sub_path: str, controller_base: Type[DataController], /,
                        name: Optional[str] = None):
        if name:
            print(f"Generating the report of {name}...")
        else:
            print(f"Generating the report in {workspace_sub_path} ({controller_base.__name__})...")

        parent_dir = self.get_workspace_path(workspace_sub_path)
        controller = controller_base()

        # Load data
        controller.load_or_update_from_data(self.get_latest_report_path(parent_dir))
        controller.load_or_update_from_gh_repo(self._repo)

        # Export data
        path_views = os.path.join(parent_dir, f"report-{datetime.utcnow().strftime('%Y%m%d')}.csv")
        controller.export_to_csv(path_views)


def main():
    traffic_parent = "traffic"
    report_gen = ReportGenerator()

    report_gen.generate_report(os.path.join(traffic_parent, "view"), TrafficViewData, name="Traffic View")
    report_gen.generate_report(os.path.join(traffic_parent, "top-referrer"), TopReferrerData, name="Top Referrer")
    report_gen.generate_report(os.path.join(traffic_parent, "top-path"), TopPathData, name="Top Path")


if __name__ == "__main__":
    main()
