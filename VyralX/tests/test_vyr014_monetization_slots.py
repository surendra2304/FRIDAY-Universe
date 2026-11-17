"""Unit tests for the TASK-VYR-014 monetization slots + cross-post export."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from app.services.crosspost_export import build_platform_captions, write_crosspost_bundle
from app.services.monetization import configured_affiliate_links, monetization_footer


def _settings(**overrides):
    base = {"affiliate_links_json": "", "business_email": ""}
    base.update(overrides)
    return SimpleNamespace(**base)


class TestAffiliateSlots(unittest.TestCase):
    def test_empty_config_means_empty_footer(self):
        # The invariant that protects today's uploads: nothing configured,
        # descriptions stay byte-identical.
        self.assertEqual(monetization_footer(_settings()), "")

    def test_links_come_only_from_settings(self):
        settings = _settings(
            affiliate_links_json=json.dumps(
                [{"label": "Creator mic", "url": "https://www.amazon.in/dp/EXAMPLE"}]
            )
        )
        links = configured_affiliate_links(settings)
        self.assertEqual(len(links), 1)
        footer = monetization_footer(settings)
        self.assertIn("Creator mic", footer)
        self.assertIn("https://www.amazon.in/dp/EXAMPLE", footer)
        # Mandatory disclosures ride along whenever links exist.
        self.assertIn("Disclosure:", footer)
        self.assertIn("As an Amazon Associate I earn from qualifying purchases.", footer)

    def test_non_amazon_link_skips_amazon_sentence(self):
        settings = _settings(
            affiliate_links_json=json.dumps(
                [{"label": "Gadget", "url": "https://www.flipkart.com/item/EXAMPLE"}]
            )
        )
        footer = monetization_footer(settings)
        self.assertIn("Disclosure:", footer)
        self.assertNotIn("Amazon Associate", footer)

    def test_business_email_only(self):
        footer = monetization_footer(_settings(business_email="vyralx.creator@gmail.com"))
        self.assertIn("vyralx.creator@gmail.com", footer)
        self.assertNotIn("Disclosure:", footer)

    def test_malformed_config_never_raises(self):
        self.assertEqual(configured_affiliate_links(_settings(affiliate_links_json="{oops")), [])
        self.assertEqual(
            configured_affiliate_links(
                _settings(affiliate_links_json='[{"label": 1}, {"url": "https://x"}, "junk"]')
            ),
            [],
        )


class TestCrosspostExport(unittest.TestCase):
    DESCRIPTION = (
        "A cat does the impossible.\n\n"
        "👉 Would you try this? Drop your answer below! 💬\n\n"
        "#Shorts #Viral #Cats"
    )

    def test_captions_use_shipped_metadata(self):
        captions = build_platform_captions(
            title="Cat Does The Impossible 😱 #Shorts",
            description=self.DESCRIPTION,
            tags=["shorts", "viral", "cats"],
            category="VIRAL",
        )
        self.assertIn("Cat Does The Impossible", captions["instagram_reels"])
        self.assertIn("#Shorts", captions["instagram_reels"])
        self.assertLessEqual(len(captions["tiktok"]), 150)
        self.assertIn("Would you try this?", captions["facebook_reels"])
        self.assertIn("Cat Does The Impossible", captions["youtube_shorts"])

    def test_bundle_written_with_video_copy(self):
        with TemporaryDirectory() as tmp:
            render = Path(tmp) / "render.mp4"
            render.write_bytes(b"fake-mp4-bytes")
            out = write_crosspost_bundle(
                render,
                title="T #Shorts",
                description=self.DESCRIPTION,
                tags=["shorts"],
                category="VIRAL",
                video_key="proj_1",
                export_root=Path(tmp) / "exports",
            )
            bundle = Path(out["bundle"])
            self.assertTrue((bundle / "video.mp4").is_file())
            self.assertTrue((bundle / "POST_COPY.txt").is_file())
            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["video_key"], "proj_1")
            self.assertTrue(manifest["video_copied"])
            self.assertIn("instagram_reels", manifest["platforms"])

    def test_bundle_survives_missing_render(self):
        with TemporaryDirectory() as tmp:
            out = write_crosspost_bundle(
                Path(tmp) / "nope.mp4",
                title="T #Shorts",
                description=self.DESCRIPTION,
                tags=[],
                video_key="proj_2",
                export_root=Path(tmp) / "exports",
            )
            self.assertFalse(out["video_copied"])
            self.assertTrue((Path(out["bundle"]) / "POST_COPY.txt").is_file())


if __name__ == "__main__":
    unittest.main()
