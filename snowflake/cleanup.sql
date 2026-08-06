-- Tear down every object this project created. Run as ACCOUNTADMIN or
-- SECURITYADMIN when you're done with the project and want to stop any
-- possibility of ongoing warehouse credit usage.
--
-- This is destructive and irreversible -- it drops all loaded data.

DROP DATABASE IF EXISTS RETAIL_INVENTORY;
DROP WAREHOUSE IF EXISTS RETAIL_INVENTORY_WH;

-- Uncomment if you created the optional CI service user in roles.sql:
-- DROP USER IF EXISTS RETAIL_INVENTORY_CI_USER;

DROP ROLE IF EXISTS RETAIL_INVENTORY_ROLE;
