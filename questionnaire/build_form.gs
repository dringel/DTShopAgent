/**
 * build_form.gs — Auto-generate the Digital Twin questionnaire as a Google
 * Form from questionnaire_items.csv, with responses collected in a Sheet.
 *
 * SETUP (once, ~5 minutes):
 *  0. The shipped CSV holds the real 115-item instrument (generated from
 *     questionnaire_instrument_source.md — see AUTHORING_GUIDE.md). The
 *     EX0x guard below only protects against accidental reversion.
 *  1. Create a new Google Sheet. File > Import > Upload questionnaire_items.csv
 *     (replace spreadsheet; keep the header row). Name the tab "items".
 *  2. Extensions > Apps Script. Paste this file. Run buildForm(). Authorize.
 *  3. The log prints the Form edit URL. Open it, then: Responses > link to a
 *     Sheet (this becomes the cohort master dataset).
 *  4. In Form settings: collect email = ON, limit 1 response = ON.
 *  5. Add one manual first question yourself if you prefer, or keep the
 *     scripted STUDENT_ID item as-is (course-issued pseudonym, validated).
 *
 * The response Sheet then has one row per student — the research dataset —
 * and each student's row is exported to their VM via make_persona.py.
 */

// Anchors follow the instrument source (questionnaire_instrument_source.md
// §2, BFI-style): keep in lockstep with the header note in make_persona.py.
var LIKERT5 = ['1 - Disagree strongly', '2 - Disagree a little',
               '3 - Neither agree nor disagree', '4 - Agree a little',
               '5 - Agree strongly'];

function buildForm() {
  var sheet = SpreadsheetApp.getActive().getSheetByName('items');
  var rows = sheet.getDataRange().getValues();
  var header = rows.shift(); // item_code,construct,question,response_type,options

  // Guard: refuse to build from the placeholder examples
  var codes = rows.map(function (r) { return String(r[0]); });
  if (codes.some(function (c) { return c.indexOf('EX0') === 0; })) {
    throw new Error('questionnaire_items.csv still contains EX0x example ' +
                    'rows — replace them with your own items first ' +
                    '(see AUTHORING_GUIDE.md).');
  }

  var form = FormApp.create('Digital Twin Lab — Consumer Profile (' +
                            rows.filter(function (r) { return r[0]; }).length +
                            ' items)');
  form.setDescription(
    'Answer honestly as yourself, not aspirationally — your agent will only ' +
    'be as accurate as these answers. Takes ~30 minutes. Your responses are ' +
    'stored under your course pseudonym; see the consent & data-use sheet ' +
    '(docs/CONSENT_AND_DATA_USE.md, on the LMS) for data handling and ' +
    'opt-out.');
  form.setProgressBar(true);

  // Consent capture, layered per research_protocol.md §3: these two
  // REQUIRED checkboxes at the top of the Form are the first layer
  // (timestamped with the response). Wording is in lockstep with
  // docs/CONSENT_AND_DATA_USE.md > "What you confirm" — change it there
  // first, then here (tests/test_instrument_lockstep.py guards the
  // presence of both boxes).
  form.addCheckboxItem()
      .setTitle('Understanding — I understand that my AI agent will browse ' +
                'and act (add-to-cart only) on my own logged-in amazon.in ' +
                'account; that my questionnaire answers, purchase-history ' +
                'profile, lab-session clickstream, agent logs, and verdicts ' +
                'are collected under my pseudonym; and that they are ' +
                'submitted once, as one zip, for anonymized analysis.')
      .setChoiceValues(['I understand'])
      .setRequired(true);
  form.addCheckboxItem()
      .setTitle('Consent — I consent to my pseudonymized data being used ' +
                'in this research that we conduct together in class, where ' +
                'the final anonymized cohort report is shared with the ' +
                'class, no other student receives access to my data, and ' +
                'the instructor retains the anonymized dataset for ' +
                'scientific research and potential aggregate publication.')
      .setChoiceValues(['I consent'])
      .setRequired(true);

  // Pseudonym ID (validated pattern DT2026-###). Apps Script cannot read
  // dtlab_config.env — keep this pattern in sync with DTLAB_ID_PATTERN by
  // hand (tests/test_instrument_lockstep.py cross-checks the two).
  var idItem = form.addTextItem()
      .setTitle('Your course-issued participant ID (e.g. DT2026-042)')
      .setRequired(true);
  var v = FormApp.createTextValidation()
      .requireTextMatchesPattern('DT\\d{4}-\\d{3}')
      .setHelpText('Format: DT2026-042 (on your course ID card/email)')
      .build();
  idItem.setValidation(v);

  var currentSection = null;
  rows.forEach(function (r) {
    var code = r[0], construct = r[1], question = r[2],
        type = r[3], options = r[4];
    if (!code) return;

    // New page per construct group keeps the form navigable
    var group = String(construct).split(':')[0];
    if (group !== currentSection) {
      form.addPageBreakItem().setTitle(group);
      currentSection = group;
    }

    var title = code + '. ' + question;
    if (type === 'likert5') {
      form.addMultipleChoiceItem().setTitle(title)
          .setChoiceValues(LIKERT5).setRequired(true);
    } else if (type === 'single_select') {
      form.addMultipleChoiceItem().setTitle(title)
          .setChoiceValues(String(options).split('|')).setRequired(true);
    } else if (type === 'multi_select') {
      form.addCheckboxItem().setTitle(title)
          .setChoiceValues(String(options).split('|')).setRequired(true);
    } else if (type === 'long_text') {
      form.addParagraphTextItem().setTitle(title).setRequired(true);
    } else { // short_text
      form.addTextItem().setTitle(title).setRequired(true);
    }
  });

  Logger.log('Form created. Edit URL: ' + form.getEditUrl());
  Logger.log('Share URL: ' + form.getPublishedUrl());
}
