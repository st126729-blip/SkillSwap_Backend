from django.test import TestCase
from django.urls import reverse


class Ps4PublicPagesTests(TestCase):
    """All PS4 pages must work for anonymous visitors and link back to the index."""

    slugs = ["khoa", "nam", "ha"]

    def test_index_links_to_every_persona(self):
        response = self.client.get(reverse("ps4:index"))
        self.assertEqual(response.status_code, 200)
        for slug in self.slugs:
            self.assertContains(response, reverse("ps4:persona", args=[slug]))

    def test_persona_and_scenario_pages(self):
        for slug in self.slugs:
            persona = self.client.get(reverse("ps4:persona", args=[slug]))
            scenario = self.client.get(reverse("ps4:scenario", args=[slug]))
            self.assertEqual(persona.status_code, 200)
            self.assertEqual(scenario.status_code, 200)
            self.assertContains(persona, reverse("ps4:index"))
            self.assertContains(persona, reverse("ps4:scenario", args=[slug]))
            self.assertContains(scenario, reverse("ps4:index"))

    def test_summary_pages(self):
        for name in ["findings", "requirements", "mvp"]:
            response = self.client.get(reverse(f"ps4:{name}"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, reverse("ps4:index"))

    def test_unknown_persona_is_404(self):
        response = self.client.get(reverse("ps4:persona", args=["nobody"]))
        self.assertEqual(response.status_code, 404)
