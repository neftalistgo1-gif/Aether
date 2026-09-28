import unittest

from app.integrations.mikrotik import address_list_entry_is_disabled


class MikroTikAddressListStateTests(unittest.TestCase):
    def test_only_enabled_address_list_entries_are_blocks(self) -> None:
        self.assertFalse(address_list_entry_is_disabled({}))
        self.assertFalse(address_list_entry_is_disabled({"disabled": "false"}))
        self.assertTrue(address_list_entry_is_disabled({"disabled": "true"}))
        self.assertTrue(address_list_entry_is_disabled({"disabled": True}))
