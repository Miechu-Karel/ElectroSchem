import unittest

from app.core.custom_library import existing_asset_pins_preserved


class ExistingAssetPinEditTests(unittest.TestCase):
    def setUp(self):
        self.original={"pins":[
            {"number":"1","name":"IN","identity":"pin-a","x":-40,"y":0},
            {"number":"2","name":"OUT","identity":"pin-b","x":40,"y":0},
        ]}

    def test_allows_appending_pins_and_renaming_existing_pins(self):
        updated={"pins":[
            {"number":"1","name":"INPUT","identity":"pin-a","x":-40,"y":0},
            {"number":"2","name":"OUTPUT","identity":"pin-b","x":40,"y":0},
            {"number":"3","name":"PIN3","identity":"pin-c","x":0,"y":40},
        ]}
        self.assertTrue(existing_asset_pins_preserved(self.original,updated))

    def test_rejects_removing_reordering_or_moving_existing_pins(self):
        removed={"pins":self.original["pins"][:1]}
        reordered={"pins":list(reversed(self.original["pins"]))}
        moved={"pins":[dict(self.original["pins"][0],x=-20),self.original["pins"][1]]}
        self.assertFalse(existing_asset_pins_preserved(self.original,removed))
        self.assertFalse(existing_asset_pins_preserved(self.original,reordered))
        self.assertFalse(existing_asset_pins_preserved(self.original,moved))


if __name__=="__main__":
    unittest.main()
