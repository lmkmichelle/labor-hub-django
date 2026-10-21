from django.core.paginator import Paginator
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse


def render_nav(current, pages=17):
    page_obj = Paginator(list(range(pages * 10)), 10).page(current)
    html = Template(
        '{% include "partials/_pagination.html" with page_obj=page_obj is_paginated=True %}'
    ).render(Context({"page_obj": page_obj}))
    return html


class PaginationTests(TestCase):
    def test_a_long_list_is_capped_with_ellipses(self):
        html = render_nav(9)
        for shown in (">1<", ">8<", ">9<", ">10<", ">17<"):
            self.assertIn(shown, html)
        for hidden in (">5<", ">13<"):
            self.assertNotIn(hidden, html)
        self.assertEqual(html.count("…"), 2)

    def test_short_lists_show_every_page(self):
        html = render_nav(2, pages=3)
        self.assertNotIn("…", html)
        self.assertIn(">3<", html)

    def test_nav_opts_out_of_prose_styles(self):
        # .format would add bullets and underline the numbers.
        html = render_nav(1)
        self.assertIn("not-format", html)
        self.assertIn("list-none", html)


class WorldMapPageTests(TestCase):
    def test_map_uses_the_standard_page_width(self):
        html = self.client.get(reverse("map")).content.decode()
        self.assertNotIn("max-w-screen-2xl", html)

    def test_panel_fragment_shows_counts_and_a_way_back(self):
        html = self.client.get(reverse("map_country_detail", args=["US"])).content.decode()
        self.assertIn("data-map-close", html)
        self.assertIn("0 researchers", html)


class MapCountryNamesTests(TestCase):
    def test_every_map_shape_resolves_to_a_country_with_the_site_name(self):
        import re
        from pathlib import Path
        from django.conf import settings
        from core.constants import COUNTRY_CHOICES
        from core.views import MAP_EXTRA_COUNTRY_NAMES

        names = {**dict(COUNTRY_CHOICES), **MAP_EXTRA_COUNTRY_NAMES}
        svg = (Path(settings.BASE_DIR) / "templates/partials/world.svg").read_text()
        for shape_id, code, title in re.findall(
                r'<path id="([^"]+)"(?: data-code="([^"]+)")? title="([^"]*)"', svg):
            code = code or shape_id
            self.assertIn(code, names, shape_id)
            self.assertEqual(title, names[code], shape_id)

    def test_russia_is_one_country_drawn_as_two_shapes(self):
        html = self.client.get(reverse("map")).content.decode()
        self.assertIn('id="RU_europe" data-code="RU"', html)
        self.assertIn('id="RU_asia" data-code="RU"', html)

    def test_the_two_congos_have_different_names(self):
        from core.constants import COUNTRY_CHOICES
        names = dict(COUNTRY_CHOICES)
        self.assertNotEqual(names["CG"], names["CD"])


class VersionedStaticTests(TestCase):
    def test_scripts_carry_a_version_so_a_deploy_busts_the_browser_cache(self):
        html = self.client.get(reverse("map")).content.decode()
        self.assertRegex(html, r'/static/js/map\.js\?v=\w+')

    def test_deploy_tree_id_is_the_version_on_upsun(self):
        from unittest import mock
        from core.templatetags.static_version import static_v
        with mock.patch.dict("os.environ", {"PLATFORM_TREE_ID": "abcdef1234567890"}):
            self.assertTrue(static_v("js/map.js").endswith("?v=abcdef123456"))
