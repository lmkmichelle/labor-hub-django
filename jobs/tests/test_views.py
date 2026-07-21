from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from jobs.models import Job


def make_job(title="Job", deadline_offset=10, url="https://example.com",
             description="Details", countries=None, students=False):
    return Job.objects.create(
        title=title,
        description=description,
        url=url,
        deadline=timezone.localdate() + timedelta(days=deadline_offset),
        countries=countries or [],
        is_for_graduate_students=students,
    )


class JobsListViewTests(TestCase):
    def test_list_renders(self):
        response = self.client.get(reverse("jobs-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs/job_list.html")

    def test_audience_students_filters_grad_jobs(self):
        grad = make_job(title="Predoc", students=True)
        faculty = make_job(title="Full Professor", students=False)
        response = self.client.get(reverse("jobs-list"), {"audience": "students"})
        self.assertIn(grad, response.context["jobs"])
        self.assertNotIn(faculty, response.context["jobs"])

    def test_search_filters_by_title(self):
        match = make_job(title="Labor Economist")
        other = make_job(title="Unrelated Role")
        response = self.client.get(reverse("jobs-list"), {"q": "Labor"})
        self.assertIn(match, response.context["jobs"])
        self.assertNotIn(other, response.context["jobs"])

    def test_country_filter(self):
        match = make_job(title="US Role", countries=["US"])
        other = make_job(title="CA Role", countries=["CA"])
        response = self.client.get(reverse("jobs-list"), {"countries": "US"})
        self.assertIn(match, response.context["jobs"])
        self.assertNotIn(other, response.context["jobs"])

    def test_filter_querystring_in_context(self):
        response = self.client.get(reverse("jobs-list"), {"q": "abc", "sort": "newest"})
        querystring = response.context["filter_querystring"]
        self.assertIn("q=abc", querystring)
        self.assertIn("sort=newest", querystring)

    def test_pagination_limits_to_ten(self):
        for i in range(11):
            make_job(title=f"Job {i}", deadline_offset=i + 1)
        response = self.client.get(reverse("jobs-list"))
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["jobs"]), 10)


class JobDetailViewTests(TestCase):
    def test_detail_renders(self):
        job = make_job()
        response = self.client.get(reverse("job-detail", kwargs={"pk": job.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs/job_detail.html")


class JobCreateViewTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="poster@example.com", password="testpass123",
            first_name="Post", last_name="Er", is_active=True,
        )

    def test_requires_login(self):
        response = self.client.get(reverse("job-create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_authenticated_user_can_create(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("job-create"), {
            "title": "New Job",
            "country_code": "US",
            "description": "A job posting.",
            "url": "https://jobs.example.com",
            "deadline": (timezone.localdate() + timedelta(days=30)).isoformat(),
            "is_for_graduate_students": "on",
        })
        self.assertEqual(Job.objects.count(), 1)
        job = Job.objects.get()
        self.assertEqual(job.uploader, self.user)
        self.assertEqual(job.countries, ["US"])
        self.assertRedirects(response, reverse("jobs-list"))
