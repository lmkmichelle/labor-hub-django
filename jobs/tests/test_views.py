from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from jobs.models import Job


def make_job(title="Job", deadline_offset=10, url="https://example.com",
             description="Details", countries=None, categories=None, status="approved"):
    return Job.objects.create(
        title=title,
        description=description,
        url=url,
        deadline=timezone.localdate() + timedelta(days=deadline_offset),
        countries=countries or [],
        categories=categories or [],
        status=status,
    )


class JobsListViewTests(TestCase):
    def test_list_renders(self):
        response = self.client.get(reverse("jobs-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "jobs/job_list.html")

    def test_audience_students_filters_junior_jobs(self):
        junior = make_job(title="Predoc", categories=["predoc"])
        senior = make_job(title="Full Professor", categories=["full_professor"])
        response = self.client.get(reverse("jobs-list"), {"audience": "students"})
        self.assertIn(junior, response.context["jobs"])
        self.assertNotIn(senior, response.context["jobs"])

    def test_category_filter(self):
        match = make_job(title="Assistant Prof", categories=["assistant_professor"])
        other = make_job(title="Predoc Role", categories=["predoc"])
        response = self.client.get(
            reverse("jobs-list"), {"category": "assistant_professor"})
        self.assertIn(match, response.context["jobs"])
        self.assertNotIn(other, response.context["jobs"])

    def test_sort_by_location(self):
        us = make_job(title="US Role", countries=["US"])
        ca = make_job(title="CA Role", countries=["CA"])
        response = self.client.get(reverse("jobs-list"), {"sort": "location"})
        jobs = list(response.context["jobs"])
        self.assertLess(jobs.index(ca), jobs.index(us))

    def test_search_filters_by_title(self):
        match = make_job(title="Labor Economist")
        other = make_job(title="Unrelated Role")
        response = self.client.get(reverse("jobs-list"), {"q": "Labor"})
        self.assertIn(match, response.context["jobs"])
        self.assertNotIn(other, response.context["jobs"])

    def test_pending_jobs_hidden(self):
        approved = make_job(title="Approved")
        pending = make_job(title="Pending", status="pending")
        response = self.client.get(reverse("jobs-list"))
        self.assertIn(approved, response.context["jobs"])
        self.assertNotIn(pending, response.context["jobs"])

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

    def test_pending_job_hidden_from_anonymous(self):
        job = make_job(status="pending")
        response = self.client.get(reverse("job-detail", kwargs={"pk": job.pk}))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_pending_job(self):
        owner = CustomUser.objects.create_user(
            email="owner@example.com", password="pw12345",
            first_name="Own", last_name="Er", is_active=True,
        )
        job = make_job(status="pending")
        job.uploader = owner
        job.save()
        self.client.force_login(owner)
        response = self.client.get(reverse("job-detail", kwargs={"pk": job.pk}))
        self.assertEqual(response.status_code, 200)


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
            "categories": ["postdoc"],
        })
        self.assertEqual(Job.objects.count(), 1)
        job = Job.objects.get()
        self.assertEqual(job.uploader, self.user)
        self.assertEqual(job.countries, ["US"])
        self.assertEqual(job.categories, ["postdoc"])
        self.assertEqual(job.status, "pending")
        self.assertRedirects(response, reverse("jobs-list"))
