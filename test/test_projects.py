import unittest

from ghrel.__main__ import get_projects


class TestProjects(unittest.TestCase):
    def test_get_projects(self):
        config = dict()
        prj = get_projects(config)
        self.assertEqual(prj, {})
        #
        config = dict(username="user", outdir="path", target=dict())
        prj = get_projects(config)
        self.assertEqual(prj, {"target": {}})
        #
        config = dict(username="user", outdir="path", target=dict(project="user/prj"))
        prj = get_projects(config)
        self.assertEqual(prj, {"target": {"project": "user/prj"}})
        #
        config = dict(
            username="user",
            outdir="path",
            tools=dict(
                project1=dict(), project2=dict(project="user/prj"), name="dummy"
            ),
        )
        prj = get_projects(config)
        self.assertEqual(
            prj, {"tools.project1": {}, "tools.project2": {"project": "user/prj"}}
        )
        #
