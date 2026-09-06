/**
 * PEDNE SEWA TRUST — EMPLOYMENT FACILITATION PLATFORM
 * Google Apps Script Cloud Backup Web App Gateway
 * 
 * Columnar Tabular Backup Schema (Version 2.1)
 * 
 * INSTRUCTIONS FOR DEPLOYMENT:
 * ==============================================================================
 * 1. Open your Google Sheet (e.g. "Pedne Sewa Trust - Candidates").
 * 2. In Google Sheets menu, click: Extensions -> Apps Script.
 * 3. In Project Settings (gear icon on left):
 *    - Click "Add script property"
 *    - Property: BACKUP_API_KEY
 *    - Value: <choose a strong secure key or enter your existing key>
 *    - Click "Save script properties".
 * 4. In Code.gs, replace the entire contents with this file.
 * 5. Click "Save" (Ctrl+S).
 * 6. Click "Deploy" -> "New deployment" (or Manage Deployments -> edit -> new version):
 *    - Type: Web app
 *    - Description: "Pedne Sewa Trust Columnar Backup Gateway v2.1"
 *    - Execute as: "Me"
 *    - Who has access: "Anyone"
 * 7. Click "Deploy" and authorize when prompted.
 * 8. Copy the Web App URL (https://script.google.com/macros/s/.../exec).
 * 9. Set the URL and API key in the desktop app (Settings screen).
 * ==============================================================================
 */

// 45 Canonical Candidate Column Definitions
var CANONICAL_COLUMNS = [
  { key: "candidate_id", header: "Candidate ID" },
  { key: "registration_date", header: "Registration Date" },
  { key: "full_name", header: "Full Name" },
  { key: "dob", header: "DOB" },
  { key: "age", header: "Age" },
  { key: "gender", header: "Gender" },
  { key: "address", header: "Address" },
  { key: "village", header: "Village" },
  { key: "vaddo", header: "Vaddo / Ward" },
  { key: "polling_booth", header: "Polling Booth" },
  { key: "taluka", header: "Taluka" },
  { key: "pincode", header: "Pincode" },
  { key: "mobile", header: "Mobile" },
  { key: "alternate_mobile", header: "Alternate Mobile" },
  { key: "email", header: "Email" },
  { key: "highest_qualification", header: "Highest Qualification" },
  { key: "course", header: "Course" },
  { key: "specialisation", header: "Specialisation" },
  { key: "institution", header: "Institution" },
  { key: "passing_year", header: "Passing Year" },
  { key: "skills", header: "Skills" },
  { key: "certifications", header: "Certifications" },
  { key: "employment_status", header: "Employment Status" },
  { key: "employment_category", header: "Employment Category" },
  { key: "organisation", header: "Organisation" },
  { key: "designation", header: "Designation" },
  { key: "work_location", header: "Work Location" },
  { key: "years_experience", header: "Years Experience" },
  { key: "previous_experience", header: "Previous Experience" },
  { key: "applied_government_job", header: "Applied Government Job" },
  { key: "government_post", header: "Government Application/Post" },
  { key: "government_app_year", header: "Government Application Year" },
  { key: "government_result_status", header: "Government Result Status" },
  { key: "self_employment_details", header: "Self Employment Details" },
  { key: "preferred_sector", header: "Preferred Sector" },
  { key: "preferred_role", header: "Preferred Role" },
  { key: "preferred_location", header: "Preferred Location" },
  { key: "willing_to_relocate", header: "Willing to Relocate" },
  { key: "preferred_employment_type", header: "Preferred Employment Type" },
  { key: "languages", header: "Languages" },
  { key: "recruiter_consent_status", header: "Recruiter Consent Status" },
  { key: "recruiter_consent_date", header: "Recruiter Consent Date" },
  { key: "remarks", header: "Remarks" },
  { key: "created_at", header: "Created At" },
  { key: "updated_at", header: "Updated At" }
];

/**
 * HTTP POST entrypoint for incoming candidate backup transmissions.
 */
function doPost(e) {
  var lock = LockService.getScriptLock();
  var lockAcquired = lock.tryLock(30000);
  
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return createJsonResponse({ status: "ERROR", message: "No post data received" }, 400);
    }

    var payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return createJsonResponse({ status: "ERROR", message: "Malformed JSON" }, 400);
    }

    var authResult = validateApiKey(payload.api_key);
    if (!authResult.valid) return createJsonResponse({ status: "ERROR", message: authResult.error }, 401);

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    if (!ss) {
      var propId = PropertiesService.getScriptProperties().getProperty("SPREADSHEET_ID") || "1DC9TY2D2_mJgyJJ_hM3a91UsSOuqssWiBuMKhaxoW_0";
      try {
        ss = SpreadsheetApp.openById(propId);
      } catch (openErr) {
        return createJsonResponse({
          status: "ERROR",
          message: "Failed to open spreadsheet: " + openErr.toString()
        }, 500);
      }
    }

    var sheetName = "Candidates";
    var sheet = ss.getSheetByName(sheetName);
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
    }

    // 4. Upsert candidates into columnar tabular sheet
    var candidates = payload.candidates || [];
    var result = upsertCandidates(sheet, candidates);

    return createJsonResponse({
      status: "SUCCESS",
      message: "Cloud backup completed successfully.",
      records_processed: candidates.length,
      records_inserted: result.inserted,
      records_updated: result.updated,
      total_records_in_sheet: result.totalInSheet,
      timestamp: new Date().toISOString()
    }, 200);

  } catch (err) {
    return createJsonResponse({ status: "ERROR", message: "Exception: " + err.toString() }, 500);
  } finally {
    if (lockAcquired) lock.releaseLock();
  }
}

/**
 * Validates the incoming API key.
 */
function validateApiKey(apiKey) {
  var expectedKey = PropertiesService.getScriptProperties().getProperty("BACKUP_API_KEY");
  if (!expectedKey || expectedKey.trim() === "") return { valid: false, error: "Authentication configuration missing." };
  if (!apiKey || apiKey.trim() !== expectedKey.trim()) return { valid: false, error: "Authentication failed." };
  return { valid: true };
}

/**
 * Derives the complete ordered column definitions from canonical list + incoming candidate keys.
 * Ensures Candidate ID is strictly Column A.
 */
function deriveColumnDefinitions(candidates) {
  var definedKeys = {};
  var colDefs = [];

  for (var i = 0; i < CANONICAL_COLUMNS.length; i++) {
    colDefs.push(CANONICAL_COLUMNS[i]);
    definedKeys[CANONICAL_COLUMNS[i].key] = true;
    definedKeys[CANONICAL_COLUMNS[i].header] = true;
  }

  // Scan candidates for any extra fields
  for (var c = 0; c < candidates.length; c++) {
    var cand = candidates[c];
    for (var key in cand) {
      if (!cand.hasOwnProperty(key)) continue;
      // Skip diagnostic or catch-all keys
      if (key === "row_values" || key === "data" || key.indexOf("PST CONNECTION TEST") !== -1) continue;
      if (!definedKeys[key]) {
        var humanHeader = key.replace(/_/g, " ").replace(/\b\w/g, function(l) { return l.toUpperCase(); });
        colDefs.push({ key: key, header: humanHeader });
        definedKeys[key] = true;
      }
    }
  }

  return colDefs;
}

/**
 * Detects whether the current Candidates sheet has the old malformed structure:
 * e.g., contains 'row_values', 'data', 'PST CONNECTION TEST', or lacks Candidate ID in Column A.
 */
function isSheetMalformed(sheet) {
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow === 0 || lastCol === 0) return true;

  var headerValues = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  for (var i = 0; i < headerValues.length; i++) {
    var h = String(headerValues[i] || "").trim().toLowerCase();
    if (h === "row_values" || h === "data" || h.indexOf("pst connection test") !== -1) {
      return true;
    }
  }

  var col1 = String(headerValues[0] || "").trim().toLowerCase();
  if (col1 !== "candidate id" && col1 !== "candidate_id") {
    return true;
  }

  return false;
}

/**
 * Formats Row 1 with an executive dark-blue theme and freezes the top row.
 */
function formatHeaderRow(sheet, colCount) {
  var headerRange = sheet.getRange(1, 1, 1, colCount);
  headerRange.setBackground("#0F172A");
  headerRange.setFontColor("#FFFFFF");
  headerRange.setFontWeight("bold");
  headerRange.setFontSize(10);
  headerRange.setWrap(false);
  sheet.setFrozenRows(1);
}

/**
 * Extracts a candidate's values into a single array aligned with the sheet's header columns.
 * Leaves cells blank ("") for missing properties. Never serializes objects into cells.
 */
function extractRowForCandidate(cand, headers, keyMap) {
  var row = [];
  for (var i = 0; i < headers.length; i++) {
    var header = headers[i];
    var val = "";

    var key = keyMap[header] || header.toLowerCase().replace(/[\s\/-]+/g, "_").trim();

    if (cand.hasOwnProperty(key) && cand[key] !== null && cand[key] !== undefined) {
      val = cand[key];
    } else if (cand.hasOwnProperty(header) && cand[header] !== null && cand[header] !== undefined) {
      val = cand[header];
    } else {
      // Case-insensitive / normalized lookup
      for (var k in cand) {
        if (!cand.hasOwnProperty(k)) continue;
        var kNorm = k.toLowerCase().replace(/[\s_-]/g, "");
        var hNorm = header.toLowerCase().replace(/[\s_-]/g, "");
        var keyNorm = key.toLowerCase().replace(/[\s_-]/g, "");
        if (kNorm === hNorm || kNorm === keyNorm) {
          val = cand[k];
          break;
        }
      }
    }

    // Ensure we never put a raw object or nested structure directly into a cell
    if (typeof val === "object" && val !== null) {
      if (Array.isArray(val)) {
        val = val.join(", ");
      } else {
        val = ""; // Discard nested objects; use dedicated columns only
      }
    }

    row.push(val !== null && val !== undefined ? String(val) : "");
  }
  return row;
}

/**
 * Upserts candidates into the sheet with proper columnar tabular formatting:
 * - Cleans out malformed diagnostic / serialized columns
 * - Ensures Candidate ID is Column A
 * - Updates existing rows in place without creating duplicates
 * - Appends new rows
 */
function upsertCandidates(sheet, candidates) {
  var columnDefs = deriveColumnDefinitions(candidates);
  var headerNames = columnDefs.map(function(c) { return c.header; });

  // Build header -> key lookup map
  var keyMap = {};
  for (var c = 0; c < columnDefs.length; c++) {
    keyMap[columnDefs[c].header] = columnDefs[c].key;
  }

  // 1. Check if sheet is malformed or empty -> reset & initialize clean headers
  if (isSheetMalformed(sheet)) {
    sheet.clear();
    sheet.getRange(1, 1, 1, headerNames.length).setValues([headerNames]);
    formatHeaderRow(sheet, headerNames.length);
  }

  // 2. Read authoritative headers from Row 1
  var lastCol = sheet.getLastColumn();
  var activeHeaders = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  // Check if active headers need expansion for any newly derived columns
  if (activeHeaders.length < headerNames.length) {
    var missingHeaders = headerNames.slice(activeHeaders.length);
    sheet.getRange(1, activeHeaders.length + 1, 1, missingHeaders.length).setValues([missingHeaders]);
    formatHeaderRow(sheet, headerNames.length);
    activeHeaders = headerNames;
    lastCol = activeHeaders.length;
  }

  // 3. Build Column A Candidate ID index
  var lastRow = sheet.getLastRow();
  var idIndex = {}; // maps candidate_id -> row_number (1-indexed)

  if (lastRow > 1) {
    var idValues = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    for (var r = 0; r < idValues.length; r++) {
      var cid = String(idValues[r][0] || "").trim();
      if (cid) {
        idIndex[cid] = r + 2;
      }
    }
  }

  var updatedCount = 0;
  var rowsToAppend = [];

  // 4. Process each candidate
  for (var i = 0; i < candidates.length; i++) {
    var cand = candidates[i];
    var candidateId = String(cand.candidate_id || cand["Candidate ID"] || "").trim();
    if (!candidateId) continue;

    var rowValues = extractRowForCandidate(cand, activeHeaders, keyMap);

    if (idIndex.hasOwnProperty(candidateId)) {
      // Existing Candidate -> Update that exact row
      var targetRow = idIndex[candidateId];
      sheet.getRange(targetRow, 1, 1, rowValues.length).setValues([rowValues]);
      updatedCount++;
    } else {
      // New Candidate -> Queue for append
      rowsToAppend.push(rowValues);
      var newRow = lastRow + rowsToAppend.length;
      idIndex[candidateId] = newRow;
    }
  }

  // 5. Batch append new candidate rows
  if (rowsToAppend.length > 0) {
    var startRow = lastRow + 1;
    sheet.getRange(startRow, 1, rowsToAppend.length, activeHeaders.length).setValues(rowsToAppend);
  }

  return {
    updated: updatedCount,
    inserted: rowsToAppend.length,
    totalInSheet: Object.keys(idIndex).length
  };
}

/**
 * Diagnostic HTTP GET endpoint for operational health check.
 */
function doGet(e) {
  var hasApiKey = Boolean(PropertiesService.getScriptProperties().getProperty("BACKUP_API_KEY"));
  return createJsonResponse({
    status: "SUCCESS",
    service: "Pedne Sewa Trust Cloud Backup Gateway",
    api_key_configured: hasApiKey,
    version: "2.1.0",
    timestamp: new Date().toISOString()
  }, 200);
}

/**
 * Creates standardized HTTP JSON output with appropriate status codes.
 */
function createJsonResponse(data, statusCode) {
  var output = ContentService.createTextOutput(JSON.stringify(data));
  output.setMimeType(ContentService.MimeType.JSON);
  return output;
}
