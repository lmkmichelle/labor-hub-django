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
        self.assertIn("data-map-back", html)
        self.assertIn("0 fellows", html)
