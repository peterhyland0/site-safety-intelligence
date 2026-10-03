-- State contractor licences (WA L&I incl. expired since 2012; OR CCB active only; CA CSLB partial download).
-- Official legal names and licence numbers: a GC can enter a licence number to pin a sub's identity.
CREATE OR REPLACE TABLE licence_rows AS
SELECT 'WA L&I' AS source, ContractorLicenseNumber AS number, UBI AS entity_id, BusinessName AS name,
       NULL::VARCHAR AS dba, Address1 AS address, City AS city, upper(State) AS state, zip5(Zip) AS zip5,
       ContractorLicenseStatus AS status, try_strptime(LicenseExpirationDate, '%m/%d/%Y')::DATE AS expires,
       SpecialtyCode1Desc AS specialty
FROM read_csv('{{REFERENCE_RAW}}/wa_lni/wa_lni_general_*.csv', all_varchar = true, header = true)
UNION ALL
SELECT 'OR CCB', license_number, license_number, full_name, NULL, address, city, upper(state), zip5(zip_code),
       'ACTIVE', try_strptime(lic_exp_date, '%m/%d/%Y')::DATE, endorsement_text
FROM read_csv('{{REFERENCE_RAW}}/or_ccb/or_ccb_active_*.csv', all_varchar = true, header = true)
UNION ALL
SELECT 'CA CSLB', LicenseNo, LicenseNo, BusinessName, nullif("BUS-NAME-2", ''), MailingAddress, City, upper(State),
       zip5(ZIPCode), PrimaryStatus, try_strptime(ExpirationDate, '%m/%d/%Y')::DATE, "Classifications(s)"
FROM read_csv('{{REFERENCE_RAW}}/ca_cslb/cslb_master.csv', all_varchar = true, header = true,
              ignore_errors = true, null_padding = true);

CREATE OR REPLACE TABLE wh.ref_ext.licence AS
SELECT DISTINCT ON (source, number) source, number, entity_id, name, dba, clean_name(name) AS clean_name,
       CASE WHEN dba IS NOT NULL THEN clean_name(dba) END AS dba_clean,
       address, addr_key(address) AS addr_key, city, state, zip5, status, expires, specialty
FROM licence_rows WHERE number IS NOT NULL
ORDER BY source, number, expires DESC NULLS LAST, status, name, entity_id, address;
