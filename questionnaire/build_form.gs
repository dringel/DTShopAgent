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

// Per-item response validation, keyed by item code — the ONE home for
// validation rules (audit 5.6). Each entry receives the just-created
// Form item and applies its validation. NOTE for the Form build:
// verify the CheckboxValidation builder method name
// (requireSelectAtMost) against the live FormApp API when running this
// script — Apps Script is not lintable from the kit, so the method
// name is confirmed at build time.
var VALIDATIONS = {
  // D05 (age, short_text): must be a plausible number
  D05: function (item) {
    item.setValidation(FormApp.createTextValidation()
        .requireNumberBetween(16, 80)
        .setHelpText('Enter your age as a number (16-80).')
        .build());
  },
  // CB04 (multi_select): at most 3 selections
  CB04: function (item) {
    item.setValidation(FormApp.createCheckboxValidation()
        .requireSelectAtMost(3)
        .setHelpText('Pick at most 3.')
        .build());
  }
};

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

  // Administrative opt-out (D6): the five sensitive demographic items
  // {D04, D09, D10, D11, D12} stay in the agent-visible persona BY
  // DEFAULT; checking this OPTIONAL box removes exactly those five from
  // persona_survey.md (the research CSV is untouched). Administrative
  // field like the consent boxes — NOT an instrument item; the EX0x
  // guard and the item loop never see it, and make_persona.py finds it
  // by its SENSITIVE_OPTOUT. title prefix.
  form.addCheckboxItem()
      .setTitle('SENSITIVE_OPTOUT. Optional: exclude my sensitive ' +
                'demographic answers (sex assigned at birth, religion, ' +
                'religious attendance, family income, political views) ' +
                'from the persona file my agent reads. They remain in ' +
                'the pseudonymized research dataset either way.')
      .setChoiceValues(["Exclude them from my agent's persona"])
      .setRequired(false);

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
    var it;
    if (type === 'likert5') {
      it = form.addMultipleChoiceItem().setTitle(title)
          .setChoiceValues(LIKERT5).setRequired(true);
    } else if (type === 'single_select') {
      it = form.addMultipleChoiceItem().setTitle(title)
          .setChoiceValues(String(options).split('|')).setRequired(true);
    } else if (type === 'multi_select') {
      it = form.addCheckboxItem().setTitle(title)
          .setChoiceValues(String(options).split('|')).setRequired(true);
    } else if (type === 'long_text') {
      it = form.addParagraphTextItem().setTitle(title).setRequired(true);
    } else { // short_text
      it = form.addTextItem().setTitle(title).setRequired(true);
    }
    if (VALIDATIONS[code]) { VALIDATIONS[code](it); }
  });

  Logger.log('Form created. Edit URL: ' + form.getEditUrl());
  Logger.log('Share URL: ' + form.getPublishedUrl());
}
