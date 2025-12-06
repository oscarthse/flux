-- Verification Script for RLS Function
-- This script checks if the current_tenant_id() function is configured correctly

\echo '=== RLS Function Verification ==='
\echo ''

-- 1. Check if the function exists
\echo 'Step 1: Checking if current_tenant_id() function exists...'
SELECT
    CASE
        WHEN COUNT(*) > 0 THEN '✓ Function exists'
        ELSE '✗ Function does NOT exist - RLS will fail!'
    END as status
FROM pg_proc
WHERE proname = 'current_tenant_id';

\echo ''

-- 2. Show the function definition
\echo 'Step 2: Current function definition:'
SELECT pg_get_functiondef('current_tenant_id'::regproc) as function_definition;

\echo ''

-- 3. Test the function with a test tenant ID
\echo 'Step 3: Testing function with sample tenant ID...'
SET app.current_tenant = 'a73ba506-b078-42b3-91f6-fd168c958ee2';

SELECT
    current_tenant_id() as returned_tenant_id,
    CASE
        WHEN current_tenant_id() = 'a73ba506-b078-42b3-91f6-fd168c958ee2'::uuid
        THEN '✓ Function returns correct tenant ID'
        WHEN current_tenant_id() IS NULL
        THEN '✗ Function returns NULL - MISMATCH DETECTED! Check if function reads app.current_tenant or app.current_tenant_id'
        ELSE '? Function returns unexpected value'
    END as test_result;

\echo ''

-- 4. Check RLS policies
\echo 'Step 4: Checking RLS policies on critical tables...'
SELECT
    schemaname,
    tablename,
    policyname,
    CASE WHEN permissive = 't' THEN 'Permissive' ELSE 'Restrictive' END as policy_type,
    cmd as applies_to
FROM pg_policies
WHERE policyname = 'tenant_isolation'
ORDER BY tablename;

\echo ''
\echo '=== Verification Complete ==='
\echo ''
\echo 'Expected Results:'
\echo '- Function should exist'
\echo '- Function definition should include: current_setting(''app.current_tenant'', true)'
\echo '- Test result should show: ✓ Function returns correct tenant ID'
\echo '- Multiple tables should have tenant_isolation policies'
\echo ''
\echo 'If any test fails, run: infrastructure/production/fix_rls.sql'
