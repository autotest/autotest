UP_SQL = """
SET @group_id = (SELECT id FROM auth_group WHERE name = 'Basic Admin');

INSERT IGNORE INTO auth_group_permissions (group_id, permission_id)
SELECT @group_id, id FROM auth_permission WHERE codename IN (
  'add_droneset', 'change_droneset', 'delete_droneset', 'add_drone',
  'change_drone', 'delete_drone');
"""

DOWN_SQL = """
DELETE auth_group_permissions.* FROM
auth_group INNER JOIN auth_group_permissions ON (
  auth_group.id = auth_group_permissions.group_id)
INNER JOIN auth_permission ON (
  auth_group_permissions.permission_id = auth_permission.id)
WHERE auth_group.name = 'Basic Admin' AND codename IN (
  'add_droneset', 'change_droneset', 'delete_droneset', 'add_drone',
  'change_drone', 'delete_drone');
"""
