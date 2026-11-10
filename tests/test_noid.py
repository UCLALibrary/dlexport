import unittest

from noid import InvalidTemplateError, NamespaceError, ValidationError, mint, validate


class NoidTests(unittest.TestCase):
    def test_mint_and_validate_check_digit(self) -> None:
        identifier = mint(template="ddk", n=42)

        self.assertEqual(len(identifier), 3)
        self.assertTrue(validate(identifier))

    def test_mint_accepts_namespace_prefixes(self) -> None:
        identifier = mint(template="ddk", n=42, scheme="doi:", naa="ark:/")

        self.assertTrue(identifier.startswith("doi:ark:/"))
        self.assertTrue(validate(identifier))

    def test_mint_rejects_invalid_template(self) -> None:
        with self.assertRaises(InvalidTemplateError):
            mint(template="dx", n=1)

    def test_mint_rejects_counter_outside_namespace(self) -> None:
        with self.assertRaises(NamespaceError):
            mint(template="dd", n=100)

    def test_validate_rejects_bad_check_digit(self) -> None:
        with self.assertRaises(ValidationError):
            validate("not-a-noid")

    def test_validate_rejects_empty_identifier(self) -> None:
        with self.assertRaises(ValidationError):
            validate("")


if __name__ == "__main__":
    unittest.main()
