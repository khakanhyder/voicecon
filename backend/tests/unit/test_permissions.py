"""
Unit tests for the workspace permission matrix.

These pin the *shape* of the role model, independent of any endpoint: which
capabilities each role has, and — more importantly — which ones an admin must
never have. If someone widens `_ADMIN` to include ownership transfer or
`team:manage_admins`, these fail immediately, before any integration test gets
the chance to.
"""
import pytest

from app.core import permissions as perms


@pytest.mark.unit
class TestRoleHierarchy:
    def test_ranks_are_strictly_ordered(self):
        assert (
            perms.role_rank(perms.ROLE_VIEWER)
            < perms.role_rank(perms.ROLE_MEMBER)
            < perms.role_rank(perms.ROLE_ADMIN)
            < perms.role_rank(perms.ROLE_OWNER)
        )

    def test_unknown_role_ranks_below_everything_and_grants_nothing(self):
        assert perms.role_rank("superuser") < perms.role_rank(perms.ROLE_VIEWER)
        assert perms.permissions_for("superuser") == frozenset()
        assert perms.permissions_for("") == frozenset()
        assert perms.permissions_for(None) == frozenset()  # type: ignore[arg-type]

    def test_roles_are_case_insensitive(self):
        assert perms.has_permission("OWNER", perms.WORKSPACE_DELETE)
        assert perms.role_rank("Admin") == perms.role_rank(perms.ROLE_ADMIN)


@pytest.mark.unit
class TestPermissionSets:
    def test_each_role_is_a_superset_of_the_one_below_except_owner_only(self):
        assert perms.permissions_for(perms.ROLE_VIEWER) < perms.permissions_for(perms.ROLE_MEMBER)
        assert perms.permissions_for(perms.ROLE_MEMBER) < perms.permissions_for(perms.ROLE_ADMIN)
        assert perms.permissions_for(perms.ROLE_ADMIN) < perms.permissions_for(perms.ROLE_OWNER)

    def test_viewer_is_read_only(self):
        granted = perms.permissions_for(perms.ROLE_VIEWER)
        assert all(p.endswith(":read") for p in granted), granted

    def test_member_can_build_but_not_administer(self):
        assert perms.has_permission(perms.ROLE_MEMBER, perms.AGENTS_WRITE)
        assert perms.has_permission(perms.ROLE_MEMBER, perms.WORKFLOWS_WRITE)
        assert not perms.has_permission(perms.ROLE_MEMBER, perms.TEAM_MANAGE)
        assert not perms.has_permission(perms.ROLE_MEMBER, perms.API_KEYS_MANAGE)
        assert not perms.has_permission(perms.ROLE_MEMBER, perms.BILLING_READ)

    def test_admin_runs_the_team_but_cannot_seize_or_destroy_the_workspace(self):
        assert perms.has_permission(perms.ROLE_ADMIN, perms.TEAM_MANAGE)
        assert perms.has_permission(perms.ROLE_ADMIN, perms.API_KEYS_MANAGE)
        for withheld in (
            perms.TEAM_MANAGE_ADMINS,
            perms.BILLING_MANAGE,
            perms.WORKSPACE_DELETE,
            perms.WORKSPACE_TRANSFER_OWNERSHIP,
        ):
            assert not perms.has_permission(perms.ROLE_ADMIN, withheld), withheld

    def test_owner_has_everything(self):
        assert perms.permissions_for(perms.ROLE_OWNER) == perms.ALL_PERMISSIONS

    def test_owner_is_never_assignable(self):
        """Ownership moves only through an explicit transfer."""
        assert perms.ROLE_OWNER not in perms.ASSIGNABLE_ROLES
        assert perms.ASSIGNABLE_ROLES < perms.ALL_ROLES


@pytest.mark.unit
class TestCanActOn:
    @pytest.mark.parametrize(
        "actor,target,allowed",
        [
            # The owner may act on anyone but themselves-as-owner is handled by
            # the endpoint, not the matrix.
            (perms.ROLE_OWNER, perms.ROLE_ADMIN, True),
            (perms.ROLE_OWNER, perms.ROLE_MEMBER, True),
            (perms.ROLE_OWNER, perms.ROLE_VIEWER, True),
            # An admin runs the ranks below them...
            (perms.ROLE_ADMIN, perms.ROLE_MEMBER, True),
            (perms.ROLE_ADMIN, perms.ROLE_VIEWER, True),
            # ...but never a peer or the owner.
            (perms.ROLE_ADMIN, perms.ROLE_ADMIN, False),
            (perms.ROLE_ADMIN, perms.ROLE_OWNER, False),
            # Members and viewers manage nobody.
            (perms.ROLE_MEMBER, perms.ROLE_VIEWER, False),
            (perms.ROLE_VIEWER, perms.ROLE_VIEWER, False),
            (perms.ROLE_MEMBER, perms.ROLE_MEMBER, False),
        ],
    )
    def test_rank_decides_who_may_be_managed(self, actor, target, allowed):
        assert perms.can_act_on(actor, target) is allowed

    def test_an_unknown_role_can_neither_act_nor_be_shielded_by_rank(self):
        assert perms.can_act_on("wizard", perms.ROLE_VIEWER) is False
        assert perms.can_act_on(perms.ROLE_ADMIN, "wizard") is True

    def test_outranks_is_strict(self):
        assert perms.outranks(perms.ROLE_OWNER, perms.ROLE_ADMIN)
        assert not perms.outranks(perms.ROLE_ADMIN, perms.ROLE_ADMIN)
        assert not perms.outranks(perms.ROLE_MEMBER, perms.ROLE_ADMIN)
