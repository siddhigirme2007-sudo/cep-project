"""
modules/medical_terms.py
----------------------------------------------------------------------
Universal medical terminology, normalization, and translation.

Architecture (layered):
    OCR text
      → normalize_test_name()          ← fixes OCR garbage, finds canonical name
      → translated_test_name()         ← local dict first, Gemini fallback
      → build_explanation()            ← local templates first, Gemini fallback
      → TTS uses the final translated text

Local dictionary covers 80+ canonical tests across:
  Haematology, Biochemistry, Lipid Profile, LFT, KFT, Thyroid,
  Diabetes, Vitamins, Minerals, Electrolytes, Cardiac, Coagulation,
  Immunology/Serology, Urine, Hormones, Tumour Markers, Microbiology.

For any test NOT in the local dictionary, dynamic_translation.py calls
Gemini to generate translated name + full explanation on-the-fly.

IMPORTANT: This module never changes result values, units, or reference
ranges. Only labels and prose are translated.
"""

from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────────────────────
# 1.  OCR alias dictionary  (lowercase OCR variant → canonical English name)
#     Covers abbreviations, alternative spellings, OCR noise, fused words.
#     Add new entries here to expand recognition without touching any other file.
# ─────────────────────────────────────────────────────────────────────────────

_OCR_ALIASES: dict[str, str] = {

    # ── Haematology ──────────────────────────────────────────────────────────
    # Hemoglobin
    "hemoglobin":                 "Hemoglobin",
    "haemoglobin":                "Hemoglobin",
    "hb":                         "Hemoglobin",
    "hgb":                        "Hemoglobin",
    "hgb.":                       "Hemoglobin",
    "hb.":                        "Hemoglobin",

    # Platelet Count
    "platelet count":             "Platelet Count",
    "plateletcount":              "Platelet Count",
    "platelets count":            "Platelet Count",
    "plateletscount":             "Platelet Count",
    "platelet":                   "Platelet Count",
    "platelets":                  "Platelet Count",
    "plt":                        "Platelet Count",
    "thrombocyte count":          "Platelet Count",
    "thrombocytes":               "Platelet Count",

    # WBC / TLC
    "wbc count":                  "WBC Count",
    "wbccount":                   "WBC Count",
    "wbc":                        "WBC Count",
    "white blood cell count":     "WBC Count",
    "white blood cells":          "WBC Count",
    "white blood cell":           "WBC Count",
    "white blood count":          "WBC Count",
    "leucocyte count":            "WBC Count",
    "leukocyte count":            "WBC Count",
    "total leucocyte count":      "WBC Count",
    "total leukocyte count":      "WBC Count",
    "tlc":                        "WBC Count",
    "total wbc":                  "WBC Count",

    # RBC
    "rbc count":                  "RBC Count",
    "rbccount":                   "RBC Count",
    "rbc":                        "RBC Count",
    "red blood cell count":       "RBC Count",
    "red blood cells":            "RBC Count",
    "red blood cell":             "RBC Count",
    "erythrocyte count":          "RBC Count",
    "erythrocytes":               "RBC Count",
    "total rbc":                  "RBC Count",

    # Hematocrit / PCV
    "hematocrit":                 "Hematocrit",
    "haematocrit":                "Hematocrit",
    "hct":                        "Hematocrit",
    "pcv":                        "Hematocrit",
    "packed cell volume":         "Hematocrit",

    # MCV
    "mcv":                        "MCV",
    "mean corpuscular volume":    "MCV",

    # MCH
    "mch":                        "MCH",
    "mean corpuscular hemoglobin": "MCH",
    "mean corpuscular haemoglobin": "MCH",

    # MCHC
    "mchc":                       "MCHC",
    "mean corpuscular hemoglobin concentration": "MCHC",
    "mean corpuscular haemoglobin concentration": "MCHC",

    # RDW
    "rdw":                        "RDW",
    "red cell distribution width": "RDW",
    "red blood cell distribution width": "RDW",

    # MPV
    "mpv":                        "MPV",
    "mean platelet volume":       "MPV",

    # Neutrophils
    "neutrophils":                "Neutrophils",
    "neutrophil":                 "Neutrophils",
    "neut":                       "Neutrophils",
    "neu":                        "Neutrophils",
    "poly":                       "Neutrophils",
    "polymorphs":                 "Neutrophils",
    "segs":                       "Neutrophils",
    "segmented neutrophils":      "Neutrophils",

    # Lymphocytes
    "lymphocytes":                "Lymphocytes",
    "lymphocyte":                 "Lymphocytes",
    "lymphs":                     "Lymphocytes",
    "lymp":                       "Lymphocytes",

    # Monocytes
    "monocytes":                  "Monocytes",
    "monocyte":                   "Monocytes",
    "mono":                       "Monocytes",

    # Eosinophils
    "eosinophils":                "Eosinophils",
    "eosinophil":                 "Eosinophils",
    "eos":                        "Eosinophils",
    "eosino":                     "Eosinophils",

    # Basophils
    "basophils":                  "Basophils",
    "basophil":                   "Basophils",
    "baso":                       "Basophils",

    # ESR
    "esr":                        "ESR",
    "erythrocyte sedimentation rate": "ESR",
    "sedimentation rate":         "ESR",
    "sed rate":                   "ESR",

    # CBC / Complete Blood Count
    "cbc":                        "CBC",
    "complete blood count":       "CBC",
    "complete blood picture":     "CBC",
    "full blood count":           "CBC",
    "fbc":                        "CBC",
    "cbp":                        "CBC",

    # ── Glucose / Diabetes ────────────────────────────────────────────────────
    "blood glucose":              "Blood Glucose",
    "glucose":                    "Blood Glucose",
    "blood sugar":                "Blood Glucose",
    "random blood sugar":         "Random Blood Sugar",
    "rbs":                        "Random Blood Sugar",
    "random blood glucose":       "Random Blood Sugar",
    "fasting blood sugar":        "Fasting Blood Sugar",
    "fasting blood glucose":      "Fasting Blood Sugar",
    "fbs":                        "Fasting Blood Sugar",
    "fbg":                        "Fasting Blood Sugar",
    "ppbs":                       "Post-Prandial Blood Sugar",
    "postprandial blood sugar":   "Post-Prandial Blood Sugar",
    "post prandial blood sugar":  "Post-Prandial Blood Sugar",
    "2 hour ppbs":                "Post-Prandial Blood Sugar",
    "hba1c":                      "HbA1c",
    "hb a1c":                     "HbA1c",
    "a1c":                        "HbA1c",
    "hemoglobin a1c":             "HbA1c",
    "haemoglobin a1c":            "HbA1c",
    "glycated hemoglobin":        "HbA1c",
    "glycosylated hemoglobin":    "HbA1c",
    "glycohemoglobin":            "HbA1c",

    # ── Lipid Profile ─────────────────────────────────────────────────────────
    "total cholesterol":          "Total Cholesterol",
    "cholesterol total":          "Total Cholesterol",
    "cholesterol":                "Total Cholesterol",
    "serum cholesterol":          "Total Cholesterol",
    "triglycerides":              "Triglycerides",
    "triglyceride":               "Triglycerides",
    "tg":                         "Triglycerides",
    "trigs":                      "Triglycerides",
    "hdl cholesterol":            "HDL Cholesterol",
    "hdl":                        "HDL Cholesterol",
    "hdl-c":                      "HDL Cholesterol",
    "hdl chol":                   "HDL Cholesterol",
    "high density lipoprotein":   "HDL Cholesterol",
    "ldl cholesterol":            "LDL Cholesterol",
    "ldl":                        "LDL Cholesterol",
    "ldl-c":                      "LDL Cholesterol",
    "ldl chol":                   "LDL Cholesterol",
    "low density lipoprotein":    "LDL Cholesterol",
    "vldl":                       "VLDL Cholesterol",
    "vldl cholesterol":           "VLDL Cholesterol",
    "very low density lipoprotein": "VLDL Cholesterol",
    "non hdl cholesterol":        "Non-HDL Cholesterol",
    "non-hdl":                    "Non-HDL Cholesterol",

    # ── Liver Function Tests (LFT) ────────────────────────────────────────────
    "alt":                        "ALT/SGPT",
    "sgpt":                       "ALT/SGPT",
    "alt/sgpt":                   "ALT/SGPT",
    "alt sgpt":                   "ALT/SGPT",
    "alanine aminotransferase":   "ALT/SGPT",
    "alanine transaminase":       "ALT/SGPT",
    "ast":                        "AST/SGOT",
    "sgot":                       "AST/SGOT",
    "ast/sgot":                   "AST/SGOT",
    "ast sgot":                   "AST/SGOT",
    "aspartate aminotransferase": "AST/SGOT",
    "aspartate transaminase":     "AST/SGOT",
    "bilirubin":                  "Bilirubin",
    "total bilirubin":            "Bilirubin",
    "t. bilirubin":               "Bilirubin",
    "t.bilirubin":                "Bilirubin",
    "serum bilirubin":            "Bilirubin",
    "tbil":                       "Bilirubin",
    "direct bilirubin":           "Direct Bilirubin",
    "bilirubin direct":           "Direct Bilirubin",
    "dbil":                       "Direct Bilirubin",
    "indirect bilirubin":         "Indirect Bilirubin",
    "bilirubin indirect":         "Indirect Bilirubin",
    "ibil":                       "Indirect Bilirubin",
    "alkaline phosphatase":       "Alkaline Phosphatase",
    "alp":                        "Alkaline Phosphatase",
    "alkphos":                    "Alkaline Phosphatase",
    "ggt":                        "GGT",
    "gamma gt":                   "GGT",
    "gamma glutamyl transferase": "GGT",
    "gamma glutamyltransferase":  "GGT",
    "gamma-gt":                   "GGT",
    "albumin":                    "Albumin",
    "serum albumin":              "Albumin",
    "globulin":                   "Globulin",
    "total protein":              "Total Protein",
    "serum total protein":        "Total Protein",
    "a/g ratio":                  "A/G Ratio",
    "albumin globulin ratio":     "A/G Ratio",

    # ── Kidney Function Tests (KFT) ───────────────────────────────────────────
    "creatinine":                 "Creatinine",
    "creatinin":                  "Creatinine",
    "serum creatinine":           "Creatinine",
    "s creatinine":               "Creatinine",
    "urea":                       "Urea",
    "blood urea":                 "Urea",
    "serum urea":                 "Urea",
    "blood urea nitrogen":        "Blood Urea Nitrogen",
    "bun":                        "Blood Urea Nitrogen",
    "uric acid":                  "Uric Acid",
    "serum uric acid":            "Uric Acid",
    "sua":                        "Uric Acid",
    "egfr":                       "eGFR",
    "estimated gfr":              "eGFR",
    "glomerular filtration rate": "eGFR",
    "gfr":                        "eGFR",

    # ── Thyroid Function Tests ─────────────────────────────────────────────────
    "tsh":                        "TSH",
    "thyroid stimulating hormone": "TSH",
    "thyroid stimulatinghormone": "TSH",
    "thyrotropin":                "TSH",
    "t3":                         "T3",
    "triiodothyronine":           "T3",
    "total t3":                   "T3",
    "t4":                         "T4",
    "thyroxine":                  "T4",
    "total t4":                   "T4",
    "free t3":                    "Free T3",
    "ft3":                        "Free T3",
    "free triiodothyronine":      "Free T3",
    "free t4":                    "Free T4",
    "ft4":                        "Free T4",
    "free thyroxine":             "Free T4",

    # ── Vitamins ─────────────────────────────────────────────────────────────
    "vitamin b12":                "Vitamin B12",
    "vit b12":                    "Vitamin B12",
    "b12":                        "Vitamin B12",
    "cobalamin":                  "Vitamin B12",
    "cyanocobalamin":             "Vitamin B12",
    "vitamin d":                  "Vitamin D",
    "vit d":                      "Vitamin D",
    "25-oh vitamin d":            "Vitamin D",
    "25 oh vitamin d":            "Vitamin D",
    "25-hydroxyvitamin d":        "Vitamin D",
    "25(oh)d":                    "Vitamin D",
    "25 hydroxyvitamin d":        "Vitamin D",
    "vitamin d total":            "Vitamin D",
    "vitamin d3":                 "Vitamin D",
    "cholecalciferol":            "Vitamin D",
    "vitamin b9":                 "Folate",
    "folic acid":                 "Folate",
    "folate":                     "Folate",
    "vitamin c":                  "Vitamin C",
    "ascorbic acid":              "Vitamin C",
    "vitamin a":                  "Vitamin A",
    "retinol":                    "Vitamin A",
    "vitamin e":                  "Vitamin E",
    "tocopherol":                 "Vitamin E",
    "vitamin k":                  "Vitamin K",

    # ── Minerals / Electrolytes ───────────────────────────────────────────────
    "calcium":                    "Calcium",
    "serum calcium":              "Calcium",
    "ca":                         "Calcium",
    "ca++":                       "Calcium",
    "phosphorus":                 "Phosphorus",
    "serum phosphorus":           "Phosphorus",
    "phosphate":                  "Phosphorus",
    "inorganic phosphorus":       "Phosphorus",
    "p":                          "Phosphorus",
    "sodium":                     "Sodium",
    "serum sodium":               "Sodium",
    "na":                         "Sodium",
    "na+":                        "Sodium",
    "potassium":                  "Potassium",
    "serum potassium":            "Potassium",
    "k":                          "Potassium",
    "k+":                         "Potassium",
    "chloride":                   "Chloride",
    "serum chloride":             "Chloride",
    "cl":                         "Chloride",
    "cl-":                        "Chloride",
    "bicarbonate":                "Bicarbonate",
    "serum bicarbonate":          "Bicarbonate",
    "hco3":                       "Bicarbonate",
    "co2":                        "Bicarbonate",
    "magnesium":                  "Magnesium",
    "serum magnesium":            "Magnesium",
    "mg":                         "Magnesium",
    "mg++":                       "Magnesium",
    "iron":                       "Iron",
    "serum iron":                 "Iron",
    "s. iron":                    "Iron",
    "fe":                         "Iron",
    "tibc":                       "TIBC",
    "total iron binding capacity": "TIBC",
    "transferrin":                "Transferrin",
    "ferritin":                   "Ferritin",
    "serum ferritin":             "Ferritin",
    "zinc":                       "Zinc",
    "serum zinc":                 "Zinc",
    "copper":                     "Copper",
    "serum copper":               "Copper",

    # ── Cardiac Markers ───────────────────────────────────────────────────────
    "crp":                        "CRP",
    "c reactive protein":         "CRP",
    "c-reactive protein":         "CRP",
    "hs crp":                     "hs-CRP",
    "hs-crp":                     "hs-CRP",
    "high sensitivity crp":       "hs-CRP",
    "hscrp":                      "hs-CRP",
    "troponin":                   "Troponin",
    "troponin i":                 "Troponin I",
    "troponin t":                 "Troponin T",
    "tnti":                       "Troponin I",
    "tnt":                        "Troponin T",
    "cpk":                        "CPK",
    "creatine phosphokinase":     "CPK",
    "creatine kinase":            "CPK",
    "ck":                         "CPK",
    "cpk mb":                     "CPK-MB",
    "ck mb":                      "CPK-MB",
    "ck-mb":                      "CPK-MB",
    "ldh":                        "LDH",
    "lactate dehydrogenase":      "LDH",
    "bnp":                        "BNP",
    "brain natriuretic peptide":  "BNP",
    "nt pro bnp":                 "NT-proBNP",
    "nt-probnp":                  "NT-proBNP",
    "homocysteine":               "Homocysteine",

    # ── Coagulation / Clotting ─────────────────────────────────────────────────
    "pt":                         "Prothrombin Time",
    "prothrombin time":           "Prothrombin Time",
    "inr":                        "INR",
    "international normalised ratio": "INR",
    "international normalized ratio": "INR",
    "aptt":                       "APTT",
    "activated partial thromboplastin time": "APTT",
    "ptt":                        "APTT",
    "fibrinogen":                 "Fibrinogen",
    "d dimer":                    "D-Dimer",
    "d-dimer":                    "D-Dimer",
    "ddimer":                     "D-Dimer",
    "bleeding time":              "Bleeding Time",
    "bt":                         "Bleeding Time",
    "clotting time":              "Clotting Time",
    "ct":                         "Clotting Time",

    # ── Hormones ─────────────────────────────────────────────────────────────
    "testosterone":               "Testosterone",
    "total testosterone":         "Testosterone",
    "free testosterone":          "Free Testosterone",
    "estradiol":                  "Estradiol",
    "e2":                         "Estradiol",
    "oestradiol":                 "Estradiol",
    "progesterone":               "Progesterone",
    "lh":                         "LH",
    "luteinizing hormone":        "LH",
    "luteinising hormone":        "LH",
    "fsh":                        "FSH",
    "follicle stimulating hormone": "FSH",
    "follicle-stimulating hormone": "FSH",
    "prolactin":                  "Prolactin",
    "prl":                        "Prolactin",
    "cortisol":                   "Cortisol",
    "serum cortisol":             "Cortisol",
    "insulin":                    "Insulin",
    "fasting insulin":            "Insulin",
    "acth":                       "ACTH",
    "adrenocorticotropic hormone": "ACTH",
    "dhea":                       "DHEA",
    "dheas":                      "DHEA-S",
    "dhea sulfate":               "DHEA-S",
    "igf 1":                      "IGF-1",
    "igf-1":                      "IGF-1",
    "growth hormone":             "Growth Hormone",
    "gh":                         "Growth Hormone",
    "pth":                        "PTH",
    "parathyroid hormone":        "PTH",
    "parathormone":               "PTH",
    "amh":                        "AMH",
    "anti mullerian hormone":     "AMH",
    "anti-mullerian hormone":     "AMH",

    # ── Immunology / Serology ─────────────────────────────────────────────────
    "ana":                        "ANA",
    "antinuclear antibody":       "ANA",
    "antinuclear antibodies":     "ANA",
    "rf":                         "Rheumatoid Factor",
    "rheumatoid factor":          "Rheumatoid Factor",
    "ra factor":                  "Rheumatoid Factor",
    "anti ccp":                   "Anti-CCP",
    "anti-ccp":                   "Anti-CCP",
    "anticitrullinated peptide":  "Anti-CCP",
    "aso":                        "ASO Titre",
    "aslo":                       "ASO Titre",
    "antistreptolysin o":         "ASO Titre",
    "hiv":                        "HIV Antibody",
    "hiv 1 and 2":                "HIV Antibody",
    "hbsag":                      "HBsAg",
    "hepatitis b surface antigen": "HBsAg",
    "hcv":                        "HCV Antibody",
    "hepatitis c":                "HCV Antibody",
    "hbs ab":                     "HBsAb",
    "hepatitis b surface antibody": "HBsAb",
    "igg":                        "IgG",
    "immunoglobulin g":           "IgG",
    "iga":                        "IgA",
    "immunoglobulin a":           "IgA",
    "igm":                        "IgM",
    "immunoglobulin m":           "IgM",
    "ige":                        "IgE",
    "immunoglobulin e":           "IgE",
    "total ige":                  "IgE",
    "complement c3":              "Complement C3",
    "c3":                         "Complement C3",
    "complement c4":              "Complement C4",
    "c4":                         "Complement C4",
    "vdrl":                       "VDRL",
    "syphilis":                   "VDRL",
    "rpr":                        "RPR",
    "widal":                      "Widal Test",
    "widal test":                 "Widal Test",

    # ── Tumour Markers ─────────────────────────────────────────────────────────
    "psa":                        "PSA",
    "prostate specific antigen":  "PSA",
    "total psa":                  "PSA",
    "free psa":                   "Free PSA",
    "cea":                        "CEA",
    "carcinoembryonic antigen":   "CEA",
    "afp":                        "AFP",
    "alpha fetoprotein":          "AFP",
    "ca 125":                     "CA-125",
    "ca-125":                     "CA-125",
    "ca125":                      "CA-125",
    "ca 19 9":                    "CA 19-9",
    "ca 19-9":                    "CA 19-9",
    "ca199":                      "CA 19-9",
    "ca 15 3":                    "CA 15-3",
    "ca15-3":                     "CA 15-3",
    "beta hcg":                   "Beta-hCG",
    "hcg":                        "Beta-hCG",
    "human chorionic gonadotropin": "Beta-hCG",
    "s100":                       "S100",
    "s-100":                      "S100",

    # ── Urine Analysis ─────────────────────────────────────────────────────────
    "urine protein":              "Urine Protein",
    "urine glucose":              "Urine Glucose",
    "urine sugar":                "Urine Glucose",
    "urine ketones":              "Urine Ketones",
    "ketones":                    "Urine Ketones",
    "urine ph":                   "Urine pH",
    "urine specific gravity":     "Urine Specific Gravity",
    "specific gravity":           "Urine Specific Gravity",
    "sg":                         "Urine Specific Gravity",
    "urine bilirubin":            "Urine Bilirubin",
    "urine urobilinogen":         "Urobilinogen",
    "urobilinogen":               "Urobilinogen",
    "urine wbc":                  "Urine WBC",
    "urine rbc":                  "Urine RBC",
    "urine pus cells":            "Urine Pus Cells",
    "pus cells":                  "Urine Pus Cells",
    "microalbumin":               "Microalbumin",
    "urine microalbumin":         "Microalbumin",
    "urine creatinine":           "Urine Creatinine",
    "urine urea":                 "Urine Urea",
    "urine sodium":               "Urine Sodium",
    "urine potassium":            "Urine Potassium",
    "24 hour protein":            "24-Hour Urine Protein",
    "24h protein":                "24-Hour Urine Protein",

    # ── Miscellaneous / Other Common Tests ────────────────────────────────────
    "glucose tolerance":          "Glucose Tolerance Test",
    "ogtt":                       "Glucose Tolerance Test",
    "oral glucose tolerance":     "Glucose Tolerance Test",
    "glucose tolerance test":     "Glucose Tolerance Test",
    "hemoglobin electrophoresis": "Hemoglobin Electrophoresis",
    "hb electrophoresis":         "Hemoglobin Electrophoresis",
    "sickle cell":                "Sickle Cell Screen",
    "g6pd":                       "G6PD",
    "glucose 6 phosphate dehydrogenase": "G6PD",
    "amylase":                    "Amylase",
    "serum amylase":              "Amylase",
    "lipase":                     "Lipase",
    "serum lipase":               "Lipase",
    "blood culture":              "Blood Culture",
    "urine culture":              "Urine Culture",
    "stool culture":              "Stool Culture",
    "stool occult blood":         "Fecal Occult Blood",
    "fecal occult blood":         "Fecal Occult Blood",
    "occult blood":               "Fecal Occult Blood",
    "procalcitonin":              "Procalcitonin",
    "pct":                        "Procalcitonin",
    "interleukin 6":              "Interleukin-6",
    "il-6":                       "Interleukin-6",
    "il6":                        "Interleukin-6",
    "anti tpo":                   "Anti-TPO",
    "anti-tpo":                   "Anti-TPO",
    "thyroid peroxidase antibody": "Anti-TPO",
    "tpo antibody":               "Anti-TPO",
    "anti thyroglobulin":         "Anti-Thyroglobulin",
    "tg antibody":                "Anti-Thyroglobulin",
    "peripheral smear":           "Peripheral Blood Smear",
    "blood smear":                "Peripheral Blood Smear",
    "reticulocyte count":         "Reticulocyte Count",
    "retic count":                "Reticulocyte Count",
    "reticulocytes":              "Reticulocyte Count",
    "stool routine":              "Stool Examination",
    "stool examination":          "Stool Examination",
    "dengue ns1":                 "Dengue NS1 Antigen",
    "dengue ns1 antigen":         "Dengue NS1 Antigen",
    "malaria":                    "Malaria Parasite",
    "malaria parasite":           "Malaria Parasite",
    "mp":                         "Malaria Parasite",
    "typhoid":                    "Typhoid Test",
    "leptospira":                 "Leptospira IgM",
    "covid":                      "COVID-19 Antigen",
    "covid antigen":              "COVID-19 Antigen",
    "covid antibody":             "COVID-19 Antibody",
    "sars cov 2":                 "COVID-19 Antigen",
    "acetylcholine receptor":     "AChR Antibody",
    "anca":                       "ANCA",
    "anti neutrophil cytoplasmic": "ANCA",
    "ds dna":                     "Anti-dsDNA",
    "anti ds dna":                "Anti-dsDNA",
    "anti-ds-dna":                "Anti-dsDNA",
    "double stranded dna":        "Anti-dsDNA",
    "oxalic acid":                "Urine Oxalate",
    "urine oxalate":              "Urine Oxalate",
}


# ─────────────────────────────────────────────────────────────────────────────
# 2.  OCR Normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_test_name(raw_name: str) -> str:
    """
    Normalizes an OCR-extracted test name to its canonical English form.

    Strategy (in order):
    1. Exact lowercase match against _OCR_ALIASES.
    2. Exact match after stripping non-alphanumeric characters.
    3. Progressive left-prefix scan: try successively shorter substrings
       (removing rightmost tokens) — catches OCR garbage like
       "PLATELETCOUNT 3s fawn" → strips "fawn", "3s", tries "PLATELETCOUNT".
    4. Substring scan: if any alias is found as a contiguous substring of
       the cleaned key, use it (handles fused OCR like "PLATELETCOUNTfawn").
    5. Fall back to title-cased alphabetic tokens (strips numeric OCR junk).
    """
    raw_stripped = re.sub(r"\s+", " ", raw_name.strip())
    key = raw_stripped.lower()

    # Strategy 1: exact
    if key in _OCR_ALIASES:
        return _OCR_ALIASES[key]

    # Strategy 2: strip punctuation
    key_clean = re.sub(r"[^a-z0-9 ]", "", key).strip()
    if key_clean in _OCR_ALIASES:
        return _OCR_ALIASES[key_clean]

    # Strategy 3: progressive prefix (drop rightmost garbage tokens one-by-one)
    tokens = key_clean.split()
    for end in range(len(tokens) - 1, 0, -1):
        candidate = " ".join(tokens[:end])
        if candidate in _OCR_ALIASES:
            return _OCR_ALIASES[candidate]
        fused = candidate.replace(" ", "")
        if fused in _OCR_ALIASES:
            return _OCR_ALIASES[fused]

    # Strategy 4: any alias is a substring of the cleaned key
    for alias in sorted(_OCR_ALIASES.keys(), key=len, reverse=True):
        alias_fused = alias.replace(" ", "")
        if alias_fused and len(alias_fused) >= 3 and alias_fused in key_clean.replace(" ", ""):
            return _OCR_ALIASES[alias]

    # Strategy 5: title-case of alphabetic tokens only (strips numeric OCR garbage)
    clean_tokens = [t for t in raw_stripped.split() if re.search(r"[A-Za-z]", t)]
    if clean_tokens:
        return " ".join(clean_tokens).title()
    return raw_stripped.title()


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Test name translations  (local dictionary — fast, offline)
# ─────────────────────────────────────────────────────────────────────────────

_TEST_NAMES: dict[str, dict[str, str]] = {
    # ── Core haematology ──────────────────────────────────────────────────────
    "Hemoglobin":       {"en": "Hemoglobin",       "hi": "हीमोग्लोबिन",                          "mr": "हिमोग्लोबिन"},
    "Platelet Count":   {"en": "Platelet Count",   "hi": "प्लेटलेट्स की संख्या",                  "mr": "प्लेटलेट्सची संख्या"},
    "WBC Count":        {"en": "WBC Count",        "hi": "WBC संख्या (श्वेत रक्त कोशिकाएँ)",     "mr": "WBC संख्या (पांढऱ्या रक्तपेशी)"},
    "RBC Count":        {"en": "RBC Count",        "hi": "RBC संख्या (लाल रक्त कोशिकाएँ)",       "mr": "RBC संख्या (लाल रक्तपेशी)"},
    "Hematocrit":       {"en": "Hematocrit",       "hi": "हेमाटोक्रिट (PCV)",                    "mr": "हेमॅटोक्रिट (PCV)"},
    "MCV":              {"en": "MCV",              "hi": "MCV (लाल रक्त कोशिकाओं का औसत आकार)",   "mr": "MCV (लाल रक्तपेशींचा सरासरी आकार)"},
    "MCH":              {"en": "MCH",              "hi": "MCH (औसत कोशिका हीमोग्लोबिन)",          "mr": "MCH (सरासरी पेशी हिमोग्लोबिन)"},
    "MCHC":             {"en": "MCHC",             "hi": "MCHC (औसत कोशिका हीमोग्लोबिन सांद्रता)","mr": "MCHC (सरासरी पेशी हिमोग्लोबिन घनता)"},
    "RDW":              {"en": "RDW",              "hi": "RDW (लाल रक्त कोशिका वितरण चौड़ाई)",   "mr": "RDW (लाल रक्तपेशी वितरण रुंदी)"},
    "MPV":              {"en": "MPV",              "hi": "MPV (औसत प्लेटलेट आकार)",               "mr": "MPV (सरासरी प्लेटलेट आकार)"},
    "Neutrophils":      {"en": "Neutrophils",      "hi": "न्यूट्रोफिल्स",                         "mr": "न्यूट्रोफिल्स"},
    "Lymphocytes":      {"en": "Lymphocytes",      "hi": "लिम्फोसाइट्स",                          "mr": "लिम्फोसाइट्स"},
    "Monocytes":        {"en": "Monocytes",        "hi": "मोनोसाइट्स",                            "mr": "मोनोसाइट्स"},
    "Eosinophils":      {"en": "Eosinophils",      "hi": "ईओसिनोफिल्स",                           "mr": "इओसिनोफिल्स"},
    "Basophils":        {"en": "Basophils",        "hi": "बेसोफिल्स",                             "mr": "बेसोफिल्स"},
    "ESR":              {"en": "ESR",              "hi": "ESR (अवसादन दर)",                       "mr": "ESR (अवसादन दर)"},
    "CBC":              {"en": "CBC",              "hi": "CBC (पूर्ण रक्त गणना)",                 "mr": "CBC (पूर्ण रक्त गणना)"},
    # ── Glucose / Diabetes ───────────────────────────────────────────────────
    "Blood Glucose":         {"en": "Blood Glucose",         "hi": "रक्त शर्करा",                            "mr": "रक्त शर्करा"},
    "Random Blood Sugar":    {"en": "Random Blood Sugar",    "hi": "यादृच्छिक रक्त शर्करा",                 "mr": "यादृच्छिक रक्त शर्करा"},
    "Fasting Blood Sugar":   {"en": "Fasting Blood Sugar",   "hi": "उपवास रक्त शर्करा",                     "mr": "उपवास रक्त शर्करा"},
    "Post-Prandial Blood Sugar": {"en": "Post-Prandial Blood Sugar", "hi": "भोजनोपरांत रक्त शर्करा",       "mr": "जेवणानंतर रक्त शर्करा"},
    "HbA1c":                 {"en": "HbA1c",                 "hi": "HbA1c (ग्लाइकेटेड हीमोग्लोबिन)",        "mr": "HbA1c (ग्लायकेटेड हिमोग्लोबिन)"},
    "Glucose Tolerance Test":{"en": "Glucose Tolerance Test","hi": "ग्लूकोज़ टॉलरेंस टेस्ट",               "mr": "ग्लूकोज टॉलरन्स चाचणी"},
    # ── Lipid profile ────────────────────────────────────────────────────────
    "Total Cholesterol":  {"en": "Total Cholesterol",  "hi": "कुल कोलेस्ट्रॉल",                   "mr": "एकूण कोलेस्टेरॉल"},
    "Triglycerides":      {"en": "Triglycerides",      "hi": "ट्राइग्लिसराइड्स",                  "mr": "ट्रायग्लिसराइड्स"},
    "HDL Cholesterol":    {"en": "HDL Cholesterol",    "hi": "HDL कोलेस्ट्रॉल (अच्छा)",           "mr": "HDL कोलेस्टेरॉल (चांगले)"},
    "LDL Cholesterol":    {"en": "LDL Cholesterol",    "hi": "LDL कोलेस्ट्रॉल (खराब)",            "mr": "LDL कोलेस्टेरॉल (वाईट)"},
    "VLDL Cholesterol":   {"en": "VLDL Cholesterol",   "hi": "VLDL कोलेस्ट्रॉल",                  "mr": "VLDL कोलेस्टेरॉल"},
    "Non-HDL Cholesterol":{"en": "Non-HDL Cholesterol","hi": "नॉन-HDL कोलेस्ट्रॉल",              "mr": "नॉन-HDL कोलेस्टेरॉल"},
    # ── LFT ──────────────────────────────────────────────────────────────────
    "ALT/SGPT":          {"en": "ALT/SGPT",          "hi": "ALT/SGPT (यकृत एंजाइम)",              "mr": "ALT/SGPT (यकृत एन्झाइम)"},
    "AST/SGOT":          {"en": "AST/SGOT",          "hi": "AST/SGOT (यकृत एंजाइम)",              "mr": "AST/SGOT (यकृत एन्झाइम)"},
    "Bilirubin":         {"en": "Bilirubin",         "hi": "बिलीरुबिन (कुल)",                      "mr": "बिलिरुबिन (एकूण)"},
    "Direct Bilirubin":  {"en": "Direct Bilirubin",  "hi": "प्रत्यक्ष बिलीरुबिन",                 "mr": "प्रत्यक्ष बिलिरुबिन"},
    "Indirect Bilirubin":{"en": "Indirect Bilirubin","hi": "अप्रत्यक्ष बिलीरुबिन",               "mr": "अप्रत्यक्ष बिलिरुबिन"},
    "Alkaline Phosphatase":{"en":"Alkaline Phosphatase","hi":"क्षारीय फॉस्फेटेज़",                "mr": "अल्कलाईन फॉस्फेटेज"},
    "GGT":               {"en": "GGT",               "hi": "GGT (गामा-ग्लूटामिल ट्रांसफेरेज़)",   "mr": "GGT (गामा-ग्लूटामिल ट्रान्सफेरेज)"},
    "Albumin":           {"en": "Albumin",           "hi": "एल्बुमिन",                             "mr": "अल्ब्युमिन"},
    "Globulin":          {"en": "Globulin",          "hi": "ग्लोब्युलिन",                          "mr": "ग्लोब्युलिन"},
    "Total Protein":     {"en": "Total Protein",     "hi": "कुल प्रोटीन",                          "mr": "एकूण प्रथिने"},
    "A/G Ratio":         {"en": "A/G Ratio",         "hi": "एल्बुमिन-ग्लोब्युलिन अनुपात",         "mr": "अल्ब्युमिन-ग्लोब्युलिन गुणोत्तर"},
    # ── KFT ──────────────────────────────────────────────────────────────────
    "Creatinine":        {"en": "Creatinine",        "hi": "क्रिएटिनिन",                           "mr": "क्रिएटिनिन"},
    "Urea":              {"en": "Urea",              "hi": "यूरिया",                                "mr": "युरिया"},
    "Blood Urea Nitrogen":{"en":"Blood Urea Nitrogen","hi":"रक्त यूरिया नाइट्रोजन (BUN)",          "mr": "रक्त युरिया नायट्रोजन (BUN)"},
    "Uric Acid":         {"en": "Uric Acid",         "hi": "यूरिक एसिड",                           "mr": "युरिक ऍसिड"},
    "eGFR":              {"en": "eGFR",              "hi": "eGFR (अनुमानित ग्लोमेरुलर फिल्टरेशन दर)", "mr": "eGFR (अनुमानित ग्लोमेरुलर फिल्ट्रेशन दर)"},
    # ── Thyroid ──────────────────────────────────────────────────────────────
    "TSH":               {"en": "TSH",               "hi": "TSH (थायरॉइड उत्तेजक हार्मोन)",        "mr": "TSH (थायरॉइड उत्तेजक संप्रेरक)"},
    "T3":                {"en": "T3",                "hi": "T3 (ट्राईआयोडोथायरोनिन)",              "mr": "T3 (ट्रायआयडोथायरोनिन)"},
    "T4":                {"en": "T4",                "hi": "T4 (थायरोक्सिन)",                      "mr": "T4 (थायरॉक्सिन)"},
    "Free T3":           {"en": "Free T3",           "hi": "फ्री T3",                              "mr": "फ्री T3"},
    "Free T4":           {"en": "Free T4",           "hi": "फ्री T4",                              "mr": "फ्री T4"},
    "Anti-TPO":          {"en": "Anti-TPO",          "hi": "एंटी-TPO एंटीबॉडी",                    "mr": "अँटी-TPO अँटीबॉडी"},
    "Anti-Thyroglobulin":{"en": "Anti-Thyroglobulin","hi": "एंटी-थायरोग्लोब्युलिन",               "mr": "अँटी-थायरोग्लोब्युलिन"},
    # ── Vitamins ─────────────────────────────────────────────────────────────
    "Vitamin B12":       {"en": "Vitamin B12",       "hi": "विटामिन B12",                          "mr": "व्हिटॅमिन B12"},
    "Vitamin D":         {"en": "Vitamin D",         "hi": "विटामिन D",                            "mr": "व्हिटॅमिन D"},
    "Folate":            {"en": "Folate",            "hi": "फोलेट (विटामिन B9)",                   "mr": "फोलेट (व्हिटॅमिन B9)"},
    "Vitamin C":         {"en": "Vitamin C",         "hi": "विटामिन C",                            "mr": "व्हिटॅमिन C"},
    "Vitamin A":         {"en": "Vitamin A",         "hi": "विटामिन A",                            "mr": "व्हिटॅमिन A"},
    "Vitamin E":         {"en": "Vitamin E",         "hi": "विटामिन E",                            "mr": "व्हिटॅमिन E"},
    "Vitamin K":         {"en": "Vitamin K",         "hi": "विटामिन K",                            "mr": "व्हिटॅमिन K"},
    # ── Minerals / Electrolytes ───────────────────────────────────────────────
    "Calcium":           {"en": "Calcium",           "hi": "कैल्शियम",                             "mr": "कॅल्शियम"},
    "Phosphorus":        {"en": "Phosphorus",        "hi": "फॉस्फोरस",                             "mr": "फॉस्फरस"},
    "Sodium":            {"en": "Sodium",            "hi": "सोडियम",                                "mr": "सोडियम"},
    "Potassium":         {"en": "Potassium",         "hi": "पोटैशियम",                             "mr": "पोटॅशियम"},
    "Chloride":          {"en": "Chloride",          "hi": "क्लोराइड",                             "mr": "क्लोराइड"},
    "Bicarbonate":       {"en": "Bicarbonate",       "hi": "बाइकार्बोनेट",                          "mr": "बायकार्बोनेट"},
    "Magnesium":         {"en": "Magnesium",         "hi": "मैग्नीशियम",                            "mr": "मॅग्नेशियम"},
    "Iron":              {"en": "Iron",              "hi": "आयरन",                                  "mr": "आयर्न"},
    "TIBC":              {"en": "TIBC",              "hi": "TIBC (कुल आयरन बाइंडिंग क्षमता)",       "mr": "TIBC (एकूण आयर्न बाइंडिंग क्षमता)"},
    "Transferrin":       {"en": "Transferrin",       "hi": "ट्रांसफेरिन",                           "mr": "ट्रान्सफेरिन"},
    "Ferritin":          {"en": "Ferritin",          "hi": "फेरिटिन",                               "mr": "फेरिटिन"},
    "Zinc":              {"en": "Zinc",              "hi": "जिंक",                                  "mr": "झिंक"},
    "Copper":            {"en": "Copper",            "hi": "कॉपर",                                  "mr": "कॉपर"},
    # ── Cardiac markers ──────────────────────────────────────────────────────
    "CRP":               {"en": "CRP",               "hi": "CRP (C-प्रतिक्रियाशील प्रोटीन)",        "mr": "CRP (C-रिऍक्टिव प्रोटीन)"},
    "hs-CRP":            {"en": "hs-CRP",            "hi": "hs-CRP (उच्च-संवेदनशीलता CRP)",         "mr": "hs-CRP (उच्च-संवेदनशीलता CRP)"},
    "Troponin":          {"en": "Troponin",          "hi": "ट्रोपोनिन",                             "mr": "ट्रोपोनिन"},
    "Troponin I":        {"en": "Troponin I",        "hi": "ट्रोपोनिन I",                           "mr": "ट्रोपोनिन I"},
    "Troponin T":        {"en": "Troponin T",        "hi": "ट्रोपोनिन T",                           "mr": "ट्रोपोनिन T"},
    "CPK":               {"en": "CPK",               "hi": "CPK (क्रिएटिन फॉस्फोकाइनेज़)",           "mr": "CPK (क्रिएटिन फॉस्फोकायनेज)"},
    "CPK-MB":            {"en": "CPK-MB",            "hi": "CPK-MB (हृदय एंजाइम)",                  "mr": "CPK-MB (हृदय एन्झाइम)"},
    "LDH":               {"en": "LDH",               "hi": "LDH (लैक्टेट डिहाइड्रोजनेज़)",           "mr": "LDH (लॅक्टेट डिहायड्रोजनेज)"},
    "BNP":               {"en": "BNP",               "hi": "BNP (मस्तिष्क नैट्रियूरेटिक पेप्टाइड)", "mr": "BNP (ब्रेन नॅट्रियुरेटिक पेप्टाइड)"},
    "NT-proBNP":         {"en": "NT-proBNP",         "hi": "NT-proBNP",                             "mr": "NT-proBNP"},
    "Homocysteine":      {"en": "Homocysteine",      "hi": "होमोसिस्टीन",                           "mr": "होमोसिस्टीन"},
    # ── Coagulation ──────────────────────────────────────────────────────────
    "Prothrombin Time":  {"en": "Prothrombin Time",  "hi": "प्रोथ्रॉम्बिन समय (PT)",               "mr": "प्रोथ्रॉम्बिन वेळ (PT)"},
    "INR":               {"en": "INR",               "hi": "INR (अंतर्राष्ट्रीय सामान्यीकृत अनुपात)", "mr": "INR (आंतरराष्ट्रीय सामान्यीकृत गुणोत्तर)"},
    "APTT":              {"en": "APTT",              "hi": "APTT (सक्रिय आंशिक थ्रॉम्बोप्लास्टिन समय)", "mr": "APTT"},
    "Fibrinogen":        {"en": "Fibrinogen",        "hi": "फाइब्रिनोजेन",                          "mr": "फायब्रिनोजेन"},
    "D-Dimer":           {"en": "D-Dimer",           "hi": "D-डाइमर",                               "mr": "D-डायमर"},
    "Bleeding Time":     {"en": "Bleeding Time",     "hi": "रक्तस्राव समय",                         "mr": "रक्तस्राव वेळ"},
    "Clotting Time":     {"en": "Clotting Time",     "hi": "थक्का जमने का समय",                     "mr": "गठ्ठा जमण्याचा वेळ"},
    # ── Hormones ─────────────────────────────────────────────────────────────
    "Testosterone":      {"en": "Testosterone",      "hi": "टेस्टोस्टेरोन",                         "mr": "टेस्टोस्टेरॉन"},
    "Free Testosterone": {"en": "Free Testosterone", "hi": "फ्री टेस्टोस्टेरोन",                   "mr": "फ्री टेस्टोस्टेरॉन"},
    "Estradiol":         {"en": "Estradiol",         "hi": "एस्ट्राडिओल",                           "mr": "एस्ट्राडिओल"},
    "Progesterone":      {"en": "Progesterone",      "hi": "प्रोजेस्टेरोन",                         "mr": "प्रोजेस्टेरॉन"},
    "LH":                {"en": "LH",                "hi": "LH (ल्यूटिनाइजिंग हार्मोन)",            "mr": "LH (ल्युटिनायझिंग संप्रेरक)"},
    "FSH":               {"en": "FSH",               "hi": "FSH (कूप उत्तेजक हार्मोन)",             "mr": "FSH (फॉलिकल स्टिम्युलेटिंग संप्रेरक)"},
    "Prolactin":         {"en": "Prolactin",         "hi": "प्रोलैक्टिन",                           "mr": "प्रोलॅक्टिन"},
    "Cortisol":          {"en": "Cortisol",          "hi": "कॉर्टिसोल",                             "mr": "कॉर्टिसॉल"},
    "Insulin":           {"en": "Insulin",           "hi": "इंसुलिन",                               "mr": "इन्सुलिन"},
    "ACTH":              {"en": "ACTH",              "hi": "ACTH (एड्रीनोकॉर्टिकोट्रोपिक हार्मोन)", "mr": "ACTH"},
    "DHEA":              {"en": "DHEA",              "hi": "DHEA",                                  "mr": "DHEA"},
    "DHEA-S":            {"en": "DHEA-S",            "hi": "DHEA-S",                                "mr": "DHEA-S"},
    "IGF-1":             {"en": "IGF-1",             "hi": "IGF-1 (इंसुलिन-जैसा विकास कारक-1)",    "mr": "IGF-1"},
    "Growth Hormone":    {"en": "Growth Hormone",    "hi": "वृद्धि हार्मोन (GH)",                   "mr": "वाढ संप्रेरक (GH)"},
    "PTH":               {"en": "PTH",               "hi": "PTH (पैराथायरॉइड हार्मोन)",             "mr": "PTH (पॅराथायरॉइड संप्रेरक)"},
    "AMH":               {"en": "AMH",               "hi": "AMH (एंटी-मुलेरियन हार्मोन)",            "mr": "AMH (अँटी-म्यूलेरियन संप्रेरक)"},
    # ── Immunology / Serology ─────────────────────────────────────────────────
    "ANA":               {"en": "ANA",               "hi": "ANA (एंटीन्यूक्लियर एंटीबॉडी)",         "mr": "ANA (अँटिन्यूक्लियर अँटीबॉडी)"},
    "Rheumatoid Factor": {"en": "Rheumatoid Factor", "hi": "रूमेटॉइड फैक्टर (RF)",                  "mr": "र्युमेटॉइड फॅक्टर (RF)"},
    "Anti-CCP":          {"en": "Anti-CCP",          "hi": "एंटी-CCP एंटीबॉडी",                     "mr": "अँटी-CCP अँटीबॉडी"},
    "ASO Titre":         {"en": "ASO Titre",         "hi": "ASO टाइटर",                             "mr": "ASO टायटर"},
    "HIV Antibody":      {"en": "HIV Antibody",      "hi": "HIV एंटीबॉडी",                          "mr": "HIV अँटीबॉडी"},
    "HBsAg":             {"en": "HBsAg",             "hi": "HBsAg (हेपेटाइटिस B सतह एंटीजन)",       "mr": "HBsAg (हिपॅटायटिस B पृष्ठभाग प्रतिजन)"},
    "HBsAb":             {"en": "HBsAb",             "hi": "HBsAb (हेपेटाइटिस B सतह एंटीबॉडी)",    "mr": "HBsAb"},
    "HCV Antibody":      {"en": "HCV Antibody",      "hi": "HCV एंटीबॉडी (हेपेटाइटिस C)",           "mr": "HCV अँटीबॉडी (हिपॅटायटिस C)"},
    "IgG":               {"en": "IgG",               "hi": "IgG (इम्युनोग्लोब्युलिन G)",             "mr": "IgG"},
    "IgA":               {"en": "IgA",               "hi": "IgA (इम्युनोग्लोब्युलिन A)",             "mr": "IgA"},
    "IgM":               {"en": "IgM",               "hi": "IgM (इम्युनोग्लोब्युलिन M)",             "mr": "IgM"},
    "IgE":               {"en": "IgE",               "hi": "IgE (कुल इम्युनोग्लोब्युलिन E)",          "mr": "IgE (एकूण इम्युनोग्लोब्युलिन E)"},
    "Complement C3":     {"en": "Complement C3",     "hi": "कॉम्प्लीमेंट C3",                       "mr": "कॉम्प्लिमेंट C3"},
    "Complement C4":     {"en": "Complement C4",     "hi": "कॉम्प्लीमेंट C4",                       "mr": "कॉम्प्लिमेंट C4"},
    "VDRL":              {"en": "VDRL",              "hi": "VDRL (सिफलिस परीक्षण)",                  "mr": "VDRL (सिफलिस चाचणी)"},
    "RPR":               {"en": "RPR",               "hi": "RPR (सिफलिस परीक्षण)",                   "mr": "RPR (सिफलिस चाचणी)"},
    "Widal Test":        {"en": "Widal Test",        "hi": "विडाल परीक्षण (टायफॉइड)",               "mr": "विडाल चाचणी (टायफॉइड)"},
    # ── Tumour markers ────────────────────────────────────────────────────────
    "PSA":               {"en": "PSA",               "hi": "PSA (प्रोस्टेट-विशिष्ट एंटीजन)",        "mr": "PSA (प्रोस्टेट-विशिष्ट प्रतिजन)"},
    "Free PSA":          {"en": "Free PSA",          "hi": "फ्री PSA",                              "mr": "फ्री PSA"},
    "CEA":               {"en": "CEA",               "hi": "CEA (कार्सिनोएम्ब्रियोनिक एंटीजन)",    "mr": "CEA (कार्सिनोएम्ब्रायोनिक प्रतिजन)"},
    "AFP":               {"en": "AFP",               "hi": "AFP (अल्फा-फेटोप्रोटीन)",               "mr": "AFP (अल्फा-फेटोप्रोटीन)"},
    "CA-125":            {"en": "CA-125",            "hi": "CA-125 (डिम्बग्रंथि ट्यूमर मार्कर)",    "mr": "CA-125 (अंडाशय ट्यूमर मार्कर)"},
    "CA 19-9":           {"en": "CA 19-9",           "hi": "CA 19-9 (अग्नाशय ट्यूमर मार्कर)",      "mr": "CA 19-9 (स्वादुपिंड ट्यूमर मार्कर)"},
    "CA 15-3":           {"en": "CA 15-3",           "hi": "CA 15-3 (स्तन ट्यूमर मार्कर)",          "mr": "CA 15-3 (स्तन ट्यूमर मार्कर)"},
    "Beta-hCG":          {"en": "Beta-hCG",          "hi": "Beta-hCG (गर्भावस्था / ट्यूमर मार्कर)", "mr": "Beta-hCG"},
    "S100":              {"en": "S100",              "hi": "S100 (ट्यूमर मार्कर)",                  "mr": "S100 (ट्यूमर मार्कर)"},
    # ── Other common ─────────────────────────────────────────────────────────
    "Amylase":           {"en": "Amylase",           "hi": "एमिलेज़",                               "mr": "अॅमायलेज"},
    "Lipase":            {"en": "Lipase",            "hi": "लाइपेज़",                               "mr": "लायपेज"},
    "Procalcitonin":     {"en": "Procalcitonin",     "hi": "प्रोकैल्सिटोनिन",                      "mr": "प्रोकॅल्सिटोनिन"},
    "Interleukin-6":     {"en": "Interleukin-6",     "hi": "इंटरल्यूकिन-6 (IL-6)",                 "mr": "इंटरल्युकिन-6 (IL-6)"},
    "G6PD":              {"en": "G6PD",              "hi": "G6PD (ग्लूकोज़-6-फॉस्फेट डिहाइड्रोजनेज़)", "mr": "G6PD"},
    "Reticulocyte Count":{"en": "Reticulocyte Count","hi": "रेटिकुलोसाइट गणना",                   "mr": "रेटिक्युलोसाइट गणना"},
    "Peripheral Blood Smear":{"en":"Peripheral Blood Smear","hi":"परिधीय रक्त स्मीयर",            "mr": "परिधीय रक्त स्मीअर"},
    "Hemoglobin Electrophoresis":{"en":"Hemoglobin Electrophoresis","hi":"हीमोग्लोबिन इलेक्ट्रोफोरेसिस","mr":"हिमोग्लोबिन इलेक्ट्रोफोरेसिस"},
    "Fecal Occult Blood":{"en": "Fecal Occult Blood","hi": "मल में गुप्त रक्त परीक्षण",            "mr": "मलामध्ये गुप्त रक्त चाचणी"},
    "Blood Culture":     {"en": "Blood Culture",     "hi": "रक्त संस्कृति",                         "mr": "रक्त संवर्धन"},
    "Urine Culture":     {"en": "Urine Culture",     "hi": "मूत्र संस्कृति",                        "mr": "मूत्र संवर्धन"},
    "Stool Examination": {"en": "Stool Examination", "hi": "मल परीक्षण",                            "mr": "मल परीक्षण"},
    "Dengue NS1 Antigen":{"en": "Dengue NS1 Antigen","hi": "डेंगू NS1 एंटीजन",                     "mr": "डेंगू NS1 प्रतिजन"},
    "Malaria Parasite":  {"en": "Malaria Parasite",  "hi": "मलेरिया परजीवी",                        "mr": "मलेरिया परजीवी"},
    "Typhoid Test":      {"en": "Typhoid Test",      "hi": "टायफॉइड परीक्षण",                       "mr": "टायफॉइड चाचणी"},
    "COVID-19 Antigen":  {"en": "COVID-19 Antigen",  "hi": "COVID-19 एंटीजन",                       "mr": "COVID-19 प्रतिजन"},
    "COVID-19 Antibody": {"en": "COVID-19 Antibody", "hi": "COVID-19 एंटीबॉडी",                    "mr": "COVID-19 अँटीबॉडी"},
    "ANCA":              {"en": "ANCA",              "hi": "ANCA एंटीबॉडी",                         "mr": "ANCA अँटीबॉडी"},
    "Anti-dsDNA":        {"en": "Anti-dsDNA",        "hi": "एंटी-dsDNA एंटीबॉडी",                  "mr": "अँटी-dsDNA अँटीबॉडी"},
    "Microalbumin":      {"en": "Microalbumin",      "hi": "माइक्रोएल्बुमिन",                       "mr": "मायक्रोअल्ब्युमिन"},
    "24-Hour Urine Protein":{"en":"24-Hour Urine Protein","hi":"24 घंटे मूत्र प्रोटीन",            "mr": "24 तास मूत्र प्रथिने"},
    "Urine Protein":     {"en": "Urine Protein",     "hi": "मूत्र प्रोटीन",                         "mr": "मूत्र प्रथिने"},
    "Urine Glucose":     {"en": "Urine Glucose",     "hi": "मूत्र शर्करा",                          "mr": "मूत्र शर्करा"},
    "Urine pH":          {"en": "Urine pH",          "hi": "मूत्र pH",                              "mr": "मूत्र pH"},
    "Urine Specific Gravity":{"en":"Urine Specific Gravity","hi":"मूत्र विशिष्ट गुरुत्व",          "mr": "मूत्र विशिष्ट घनता"},
    "Urine Pus Cells":   {"en": "Urine Pus Cells",   "hi": "मूत्र में पस कोशिकाएँ",                "mr": "मूत्रातील पस पेशी"},
    "Urine WBC":         {"en": "Urine WBC",         "hi": "मूत्र श्वेत रक्त कोशिकाएँ",            "mr": "मूत्रातील पांढऱ्या रक्तपेशी"},
    "Urine RBC":         {"en": "Urine RBC",         "hi": "मूत्र लाल रक्त कोशिकाएँ",              "mr": "मूत्रातील लाल रक्तपेशी"},
    "Urobilinogen":      {"en": "Urobilinogen",      "hi": "यूरोबिलिनोजेन",                         "mr": "युरोबिलिनोजेन"},
    "Urine Ketones":     {"en": "Urine Ketones",     "hi": "मूत्र कीटोन",                           "mr": "मूत्र किटोन"},
    "TIBC":              {"en": "TIBC",              "hi": "TIBC (कुल आयरन बाइंडिंग क्षमता)",      "mr": "TIBC"},
}


def translated_test_name(canonical: str, lang: str) -> str:
    """
    Returns the translated test name.
    Local dictionary first → dynamic Gemini translation for unknown tests.
    """
    if lang == "en":
        return canonical
    entry = _TEST_NAMES.get(canonical)
    if entry:
        return entry.get(lang, canonical)
    # Unknown test: try Gemini
    try:
        from modules.dynamic_translation import translate_test_name_dynamic
        return translate_test_name_dynamic(canonical, lang)
    except Exception:
        return canonical


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Test descriptions (what does this test measure?)
# ─────────────────────────────────────────────────────────────────────────────

# Generic "what it measures" snippets per language for known tests.
# For unknown tests, build_explanation() falls through to dynamic_translation.
_TEST_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "Hemoglobin":     {"en": "the amount of hemoglobin — a protein in red blood cells that carries oxygen — in your blood", "hi": "आपके रक्त में हीमोग्लोबिन — लाल रक्त कोशिकाओं में ऑक्सीजन वाहक प्रोटीन — की मात्रा", "mr": "तुमच्या रक्तातील हिमोग्लोबिनचे प्रमाण — लाल रक्तपेशींमध्ये ऑक्सिजन वाहून नेणारे प्रथिन"},
    "Platelet Count": {"en": "the number of platelets — tiny cells that help your blood clot — in your blood", "hi": "आपके रक्त में प्लेटलेट्स — छोटी कोशिकाएँ जो खून जमाने में मदद करती हैं — की संख्या", "mr": "तुमच्या रक्तातील प्लेटलेट्सची संख्या — लहान पेशी ज्या रक्त गोठण्यास मदत करतात"},
    "WBC Count":      {"en": "the number of white blood cells — your immune system's defenders — in your blood", "hi": "आपके रक्त में श्वेत रक्त कोशिकाओं — प्रतिरक्षा प्रणाली के रक्षकों — की संख्या", "mr": "तुमच्या रक्तातील पांढऱ्या रक्तपेशींची संख्या — रोगप्रतिकार यंत्रणेचे रक्षक"},
    "RBC Count":      {"en": "the number of red blood cells — which carry oxygen from your lungs to your body — in your blood", "hi": "आपके रक्त में लाल रक्त कोशिकाओं — जो फेफड़ों से शरीर में ऑक्सीजन पहुँचाती हैं — की संख्या", "mr": "तुमच्या रक्तातील लाल रक्तपेशींची संख्या — ज्या फुफ्फुसातून शरीरात ऑक्सिजन वाहून नेतात"},
    "Hematocrit":     {"en": "the percentage of your blood volume made up of red blood cells", "hi": "आपके रक्त की कुल मात्रा में लाल रक्त कोशिकाओं का प्रतिशत", "mr": "तुमच्या रक्ताच्या एकूण घनफळात लाल रक्तपेशींचे प्रमाण"},
    "MCV":            {"en": "the average size of your red blood cells", "hi": "आपकी लाल रक्त कोशिकाओं का औसत आकार", "mr": "तुमच्या लाल रक्तपेशींचा सरासरी आकार"},
    "MCH":            {"en": "the average amount of hemoglobin in each red blood cell", "hi": "प्रत्येक लाल रक्त कोशिका में हीमोग्लोबिन की औसत मात्रा", "mr": "प्रत्येक लाल रक्तपेशीतील सरासरी हिमोग्लोबिनचे प्रमाण"},
    "MCHC":           {"en": "the average concentration of hemoglobin in red blood cells", "hi": "लाल रक्त कोशिकाओं में हीमोग्लोबिन की औसत सांद्रता", "mr": "लाल रक्तपेशींमध्ये हिमोग्लोबिनची सरासरी घनता"},
    "RDW":            {"en": "the variation in size of your red blood cells", "hi": "आपकी लाल रक्त कोशिकाओं के आकार में भिन्नता", "mr": "तुमच्या लाल रक्तपेशींच्या आकारातील फरक"},
    "ESR":            {"en": "how quickly red blood cells settle to the bottom of a tube — used as a general marker of inflammation", "hi": "लाल रक्त कोशिकाएँ एक ट्यूब में कितनी जल्दी नीचे बैठती हैं — सामान्य सूजन का एक संकेतक", "mr": "लाल रक्तपेशी किती वेगाने नळीच्या तळाशी बसतात — सामान्य जळजळीचा एक निर्देशक"},
    "Blood Glucose":  {"en": "the amount of sugar (glucose) in your blood", "hi": "आपके रक्त में शर्करा (ग्लूकोज़) की मात्रा", "mr": "तुमच्या रक्तातील साखर (ग्लूकोज) चे प्रमाण"},
    "Random Blood Sugar": {"en": "the sugar level in your blood at the time of the test, regardless of when you last ate", "hi": "परीक्षण के समय आपके रक्त में शर्करा का स्तर, भोजन की परवाह किए बिना", "mr": "चाचणीच्या वेळी तुमच्या रक्तातील साखरेचे प्रमाण"},
    "Fasting Blood Sugar": {"en": "the sugar level in your blood after at least 8 hours without eating", "hi": "कम से कम 8 घंटे बिना खाए आपके रक्त में शर्करा का स्तर", "mr": "किमान 8 तास न खाल्ल्यानंतर तुमच्या रक्तातील साखरेचे प्रमाण"},
    "HbA1c":          {"en": "your average blood sugar level over the past 2-3 months — a key diabetes monitoring test", "hi": "पिछले 2-3 महीनों में आपके औसत रक्त शर्करा स्तर — मधुमेह की निगरानी का एक प्रमुख परीक्षण", "mr": "मागील 2-3 महिन्यांतील सरासरी रक्त शर्करा पातळी — मधुमेह देखरेखीची एक महत्त्वाची चाचणी"},
    "Total Cholesterol": {"en": "the total amount of cholesterol — a fat-like substance — in your blood", "hi": "आपके रक्त में कोलेस्ट्रॉल — एक वसा जैसे पदार्थ — की कुल मात्रा", "mr": "तुमच्या रक्तातील एकूण कोलेस्टेरॉलचे प्रमाण"},
    "Triglycerides":  {"en": "the level of triglycerides — a type of fat stored in your blood", "hi": "ट्राइग्लिसराइड्स — एक प्रकार की वसा — का स्तर", "mr": "ट्रायग्लिसराइड्स — एक प्रकारची चरबी — चे प्रमाण"},
    "HDL Cholesterol": {"en": "HDL ('good') cholesterol — which helps remove other forms of cholesterol from the bloodstream", "hi": "HDL ('अच्छा') कोलेस्ट्रॉल — जो अन्य प्रकार के कोलेस्ट्रॉल को रक्त से हटाने में मदद करता है", "mr": "HDL ('चांगले') कोलेस्टेरॉल — जे रक्तातून इतर कोलेस्टेरॉल काढून टाकण्यास मदत करते"},
    "LDL Cholesterol": {"en": "LDL ('bad') cholesterol — which can build up in blood vessel walls", "hi": "LDL ('खराब') कोलेस्ट्रॉल — जो रक्त वाहिकाओं की दीवारों में जमा हो सकता है", "mr": "LDL ('वाईट') कोलेस्टेरॉल — जे रक्तवाहिन्यांच्या भिंतींमध्ये जमा होऊ शकते"},
    "ALT/SGPT":       {"en": "ALT — an enzyme mainly found in the liver, used to assess liver health", "hi": "ALT — मुख्यतः यकृत में पाया जाने वाला एंजाइम, यकृत के स्वास्थ्य का आकलन करता है", "mr": "ALT — मुख्यतः यकृतात आढळणारे एन्झाइम, यकृताच्या आरोग्याचे मूल्यमापन करते"},
    "AST/SGOT":       {"en": "AST — an enzyme in the liver and other tissues, used to assess liver and muscle health", "hi": "AST — यकृत और अन्य ऊतकों में पाया जाने वाला एंजाइम, यकृत और मांसपेशियों का आकलन करता है", "mr": "AST — यकृत आणि इतर ऊतींमध्ये आढळणारे एन्झाइम"},
    "Bilirubin":      {"en": "bilirubin — a yellow pigment produced when red blood cells break down, processed by the liver", "hi": "बिलीरुबिन — लाल रक्त कोशिकाओं के टूटने पर बनने वाला पीला वर्णक, यकृत द्वारा प्रसंस्कृत", "mr": "बिलिरुबिन — लाल रक्तपेशी तुटताना तयार होणारा पिवळा रंगद्रव्य, यकृताद्वारे प्रक्रिया"},
    "Alkaline Phosphatase": {"en": "alkaline phosphatase — an enzyme linked to liver and bone health", "hi": "क्षारीय फॉस्फेटेज़ — यकृत और हड्डियों के स्वास्थ्य से जुड़ा एंजाइम", "mr": "अल्कलाईन फॉस्फेटेज — यकृत आणि हाडांच्या आरोग्याशी संबंधित एन्झाइम"},
    "Creatinine":     {"en": "creatinine — a waste product of muscles, filtered out by the kidneys, used to assess kidney function", "hi": "क्रिएटिनिन — मांसपेशियों का अपशिष्ट उत्पाद, किडनी द्वारा छाना जाता है, किडनी के कार्य का आकलन करता है", "mr": "क्रिएटिनिन — स्नायूंचा टाकाऊ पदार्थ, मूत्रपिंडांद्वारे फिल्टर, मूत्रपिंडाच्या कार्याचे मूल्यमापन"},
    "Urea":           {"en": "urea — a waste product formed when the body breaks down protein, normally removed by the kidneys", "hi": "यूरिया — प्रोटीन टूटने पर बनने वाला अपशिष्ट, आमतौर पर किडनी द्वारा हटाया जाता है", "mr": "युरिया — शरीर प्रथिने मोडताना तयार होणारा टाकाऊ पदार्थ, सामान्यतः मूत्रपिंडांद्वारे काढला जातो"},
    "Blood Urea Nitrogen": {"en": "the amount of nitrogen in your blood from urea — reflecting kidney health", "hi": "यूरिया से रक्त में नाइट्रोजन की मात्रा — किडनी के स्वास्थ्य को दर्शाता है", "mr": "युरियातून रक्तातील नायट्रोजनचे प्रमाण — मूत्रपिंडाच्या आरोग्याचे प्रतिबिंब"},
    "Uric Acid":      {"en": "uric acid — a waste product from the breakdown of purines, normally excreted by the kidneys", "hi": "यूरिक एसिड — प्यूरिन के टूटने से बनने वाला अपशिष्ट, सामान्यतः किडनी द्वारा बाहर निकाला जाता है", "mr": "युरिक ऍसिड — प्युरिनच्या विघटनातून तयार होणारा टाकाऊ पदार्थ"},
    "eGFR":           {"en": "an estimate of how well your kidneys are filtering waste from your blood", "hi": "यह अनुमान कि आपकी किडनी रक्त से अपशिष्ट कितनी अच्छी तरह छान रही है", "mr": "तुमची मूत्रपिंडे रक्तातील टाकाऊ पदार्थ किती चांगल्याप्रकारे फिल्टर करत आहेत याचा अंदाज"},
    "TSH":            {"en": "TSH (thyroid-stimulating hormone) — a hormone that controls how the thyroid gland works", "hi": "TSH (थायरॉइड-उत्तेजक हार्मोन) — एक हार्मोन जो थायरॉइड ग्रंथि के कार्य को नियंत्रित करता है", "mr": "TSH (थायरॉइड-उत्तेजक संप्रेरक) — थायरॉइड ग्रंथी कशी कार्य करते हे नियंत्रित करणारे संप्रेरक"},
    "T3":             {"en": "T3 (triiodothyronine) — a thyroid hormone that regulates metabolism and energy", "hi": "T3 (ट्राईआयोडोथायरोनिन) — एक थायरॉइड हार्मोन जो चयापचय और ऊर्जा को नियंत्रित करता है", "mr": "T3 (ट्रायआयडोथायरोनिन) — चयापचय आणि ऊर्जा नियंत्रित करणारे थायरॉइड संप्रेरक"},
    "T4":             {"en": "T4 (thyroxine) — the main hormone produced by the thyroid gland", "hi": "T4 (थायरोक्सिन) — थायरॉइड ग्रंथि द्वारा उत्पादित मुख्य हार्मोन", "mr": "T4 (थायरॉक्सिन) — थायरॉइड ग्रंथीद्वारे उत्पादित मुख्य संप्रेरक"},
    "Vitamin B12":    {"en": "Vitamin B12 — essential for nerve function, red blood cell production, and DNA synthesis", "hi": "विटामिन B12 — तंत्रिका कार्य, लाल रक्त कोशिका उत्पादन और DNA संश्लेषण के लिए आवश्यक", "mr": "व्हिटॅमिन B12 — मज्जातंतू कार्य, लाल रक्तपेशी निर्मिती आणि DNA संश्लेषणासाठी आवश्यक"},
    "Vitamin D":      {"en": "Vitamin D — important for bone strength, immune function, and muscle health", "hi": "विटामिन D — हड्डियों की मजबूती, प्रतिरक्षा कार्य और मांसपेशियों के स्वास्थ्य के लिए महत्वपूर्ण", "mr": "व्हिटॅमिन D — हाडांची मजबुती, रोगप्रतिकार कार्य आणि स्नायूंच्या आरोग्यासाठी महत्त्वाचे"},
    "Folate":         {"en": "folate (Vitamin B9) — essential for cell growth and formation of DNA, especially important during pregnancy", "hi": "फोलेट (विटामिन B9) — कोशिका वृद्धि और DNA निर्माण के लिए आवश्यक, गर्भावस्था में विशेष रूप से महत्वपूर्ण", "mr": "फोलेट (व्हिटॅमिन B9) — पेशी वाढ आणि DNA निर्मितीसाठी आवश्यक"},
    "Calcium":        {"en": "calcium — a mineral essential for strong bones, muscle contraction, and nerve signaling", "hi": "कैल्शियम — मजबूत हड्डियों, मांसपेशियों के संकुचन और तंत्रिका संकेतन के लिए आवश्यक खनिज", "mr": "कॅल्शियम — मजबूत हाडे, स्नायू आकुंचन आणि मज्जातंतू संकेतांसाठी आवश्यक खनिज"},
    "Sodium":         {"en": "sodium — an electrolyte that regulates fluid balance and nerve function in the body", "hi": "सोडियम — एक इलेक्ट्रोलाइट जो शरीर में तरल संतुलन और तंत्रिका कार्य को नियंत्रित करता है", "mr": "सोडियम — एक इलेक्ट्रोलाइट जे शरीरातील द्रव संतुलन आणि मज्जातंतू कार्य नियंत्रित करते"},
    "Potassium":      {"en": "potassium — an electrolyte essential for heart rhythm, muscle function, and fluid balance", "hi": "पोटैशियम — हृदय की लय, मांसपेशी कार्य और तरल संतुलन के लिए आवश्यक इलेक्ट्रोलाइट", "mr": "पोटॅशियम — हृदयाची लय, स्नायू कार्य आणि द्रव संतुलनासाठी आवश्यक इलेक्ट्रोलाइट"},
    "Iron":           {"en": "iron — a mineral needed to produce hemoglobin and carry oxygen throughout the body", "hi": "आयरन — हीमोग्लोबिन बनाने और शरीर में ऑक्सीजन पहुँचाने के लिए आवश्यक खनिज", "mr": "आयर्न — हिमोग्लोबिन तयार करण्यासाठी आणि शरीरात ऑक्सिजन पोहोचवण्यासाठी आवश्यक खनिज"},
    "Ferritin":       {"en": "ferritin — a protein that stores iron in the body, reflecting your iron reserves", "hi": "फेरिटिन — एक प्रोटीन जो शरीर में आयरन संग्रहीत करता है, आपके आयरन भंडार को दर्शाता है", "mr": "फेरिटिन — शरीरात आयर्न साठवणारे प्रथिन, तुमच्या आयर्न साठ्याचे प्रतिबिंब"},
    "CRP":            {"en": "CRP (C-reactive protein) — a marker of inflammation produced by the liver", "hi": "CRP (C-प्रतिक्रियाशील प्रोटीन) — यकृत द्वारा उत्पन्न सूजन का एक मार्कर", "mr": "CRP (C-रिऍक्टिव प्रोटीन) — यकृताद्वारे तयार केलेला जळजळीचा निर्देशक"},
    "Troponin":       {"en": "troponin — a protein released into the blood when heart muscle is damaged", "hi": "ट्रोपोनिन — हृदय की मांसपेशी क्षतिग्रस्त होने पर रक्त में छोड़ा जाने वाला प्रोटीन", "mr": "ट्रोपोनिन — हृदयाचे स्नायू खराब झाल्यावर रक्तात सोडले जाणारे प्रथिन"},
    "INR":            {"en": "INR — a measure of how long it takes your blood to clot, used to monitor blood-thinning treatment", "hi": "INR — यह मापता है कि आपके खून को जमने में कितना समय लगता है, रक्त पतला करने के उपचार की निगरानी के लिए", "mr": "INR — तुमचे रक्त गोठण्यास किती वेळ लागतो याचे मोजमाप"},
    "D-Dimer":        {"en": "D-Dimer — a protein fragment produced when blood clots dissolve, used to evaluate clotting disorders", "hi": "D-डाइमर — रक्त के थक्के घुलने पर बनने वाला प्रोटीन टुकड़ा, थक्के विकारों का मूल्यांकन करता है", "mr": "D-डायमर — रक्ताचे गठ्ठे विरघळताना तयार होणारा प्रोटीन तुकडा"},
    "PSA":            {"en": "PSA (prostate-specific antigen) — a protein produced by the prostate gland", "hi": "PSA (प्रोस्टेट-विशिष्ट एंटीजन) — प्रोस्टेट ग्रंथि द्वारा उत्पादित एक प्रोटीन", "mr": "PSA (प्रोस्टेट-विशिष्ट प्रतिजन) — प्रोस्टेट ग्रंथीद्वारे तयार केलेले प्रथिन"},
    "HbA1c":          {"en": "your average blood glucose level over the past 2-3 months", "hi": "पिछले 2-3 महीनों में आपके औसत रक्त शर्करा स्तर", "mr": "मागील 2-3 महिन्यांतील सरासरी रक्त शर्करा पातळी"},
}


def _get_description(canonical: str, lang: str) -> str:
    """Returns the description of what the test measures in the target language."""
    entry = _TEST_DESCRIPTIONS.get(canonical)
    if entry:
        return entry.get(lang) or entry.get("en", "")
    # Generic fallback (used when Gemini is not available and test is unknown)
    generic = {
        "en": "a value measured in this laboratory test",
        "hi": "इस प्रयोगशाला जाँच में मापा गया एक मान",
        "mr": "या प्रयोगशाळा चाचणीत मोजलेले एक मूल्य",
    }
    return generic.get(lang, generic["en"])


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Status label translations
# ─────────────────────────────────────────────────────────────────────────────

STATUS_LABELS: dict[str, dict[str, str]] = {
    "Low":                 {"en": "Low",                          "hi": "कम",                                    "mr": "कमी"},
    "Normal":              {"en": "Normal",                       "hi": "सामान्य",                               "mr": "सामान्य"},
    "High":                {"en": "High",                         "hi": "अधिक",                                  "mr": "जास्त"},
    "Unable to determine": {"en": "Unable to determine",          "hi": "निर्धारित नहीं किया जा सकता",           "mr": "निर्धारित करता येत नाही"},
}


def translated_status(status: str, lang: str) -> str:
    entry = STATUS_LABELS.get(status)
    if not entry:
        return status
    return entry.get(lang, status)


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Safety notices
# ─────────────────────────────────────────────────────────────────────────────

SAFETY_NOTICES: dict[str, str] = {
    "en": (
        "For educational/report-understanding purposes only. This does not "
        "provide diagnosis or treatment. Consult a qualified healthcare professional."
    ),
    "hi": (
        "केवल शैक्षिक/रिपोर्ट समझने के उद्देश्य से। यह निदान या उपचार प्रदान "
        "नहीं करता। कृपया किसी योग्य स्वास्थ्य विशेषज्ञ से सलाह लें।"
    ),
    "mr": (
        "केवळ शैक्षणिक/अहवाल-समजून घेण्याच्या उद्देशाने. हे निदान किंवा उपचार "
        "देत नाही. कृपया पात्र वैद्यकीय तज्ञांचा सल्ला घ्या."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Build complete patient-friendly explanations
# ─────────────────────────────────────────────────────────────────────────────

def build_explanation(
    canonical: str,
    lang: str,
    status: str,
    value: str,
    unit: str,
    reference_text: str,
) -> str:
    """
    Builds a complete patient-friendly explanation in the target language.

    For tests in the local dictionary → instant template-based generation.
    For unknown tests → falls through to dynamic_translation (Gemini).
    Never changes value, unit, reference_text, or status.
    Never diagnoses or prescribes.
    """
    # If test is known locally, use templates (fast, always works offline)
    is_known = canonical in _TEST_NAMES or canonical in _TEST_DESCRIPTIONS

    if is_known:
        t_name = translated_test_name(canonical, lang)
        description = _get_description(canonical, lang)
        if lang == "hi":
            return _build_hi(t_name, description, status, value, unit, reference_text)
        elif lang == "mr":
            return _build_mr(t_name, description, status, value, unit, reference_text)
        else:
            return _build_en(t_name, description, status, value, unit, reference_text)

    # Unknown test → use dynamic Gemini-based generation
    try:
        from modules.dynamic_translation import translate_unknown_test
        result = translate_unknown_test(canonical, lang, status, value, unit, reference_text)
        return result.explanation
    except Exception:
        # Final fallback: English template
        desc = _get_description(canonical, "en")
        return _build_en(canonical, desc, status, value, unit, reference_text)


def _build_en(name: str, desc: str, status: str, value: str, unit: str, ref: str) -> str:
    unit_str = f" {unit}" if unit else ""
    ref_str = f" ({ref})" if ref else ""
    base = f"{name} measures {desc}."
    suffix = " This result alone does not determine the cause. Please discuss this with a qualified healthcare professional."
    if status == "Normal":
        return f"{base} Your result of {value}{unit_str} is within the reference range on your report{ref_str}.{suffix}"
    if status == "Low":
        return f"{base} Your result of {value}{unit_str} is below the reference range on your report{ref_str}.{suffix}"
    if status == "High":
        return f"{base} Your result of {value}{unit_str} is above the reference range on your report{ref_str}.{suffix}"
    return (
        f"{base} Your result is {value}{unit_str}. "
        "We could not reliably determine the reference range for this test from your report. "
        "Please check this with a qualified healthcare professional."
    )


def _build_hi(name: str, desc: str, status: str, value: str, unit: str, ref: str) -> str:
    unit_str = f" {unit}" if unit else ""
    ref_str = f" ({ref})" if ref else ""
    base = f"{name} की जाँच {desc} को मापती है।"
    suffix = " केवल इस परिणाम से कारण निर्धारित नहीं किया जा सकता। कृपया इस परिणाम के बारे में किसी योग्य स्वास्थ्य विशेषज्ञ से चर्चा करें।"
    if status == "Normal":
        return f"{base} आपका परिणाम {value}{unit_str} है, जो आपकी रिपोर्ट पर छपी संदर्भ सीमा{ref_str} के भीतर है।{suffix}"
    if status == "Low":
        return f"{base} आपका परिणाम {value}{unit_str} है, जो आपकी रिपोर्ट पर छपी संदर्भ सीमा{ref_str} से कम है।{suffix}"
    if status == "High":
        return f"{base} आपका परिणाम {value}{unit_str} है, जो आपकी रिपोर्ट पर छपी संदर्भ सीमा{ref_str} से अधिक है।{suffix}"
    return (
        f"{base} आपका परिणाम {value}{unit_str} है। "
        "हम आपकी रिपोर्ट से इस जाँच की संदर्भ सीमा विश्वसनीय रूप से नहीं पढ़ सके। "
        "कृपया किसी योग्य स्वास्थ्य विशेषज्ञ से इसकी जाँच कराएँ।"
    )


def _build_mr(name: str, desc: str, status: str, value: str, unit: str, ref: str) -> str:
    unit_str = f" {unit}" if unit else ""
    ref_str = f" ({ref})" if ref else ""
    base = f"{name} ही चाचणी {desc} मोजते."
    suffix = " केवळ या निकालावरून कारण निश्चित करता येत नाही. कृपया या निकालाबद्दल पात्र वैद्यकीय तज्ञांशी चर्चा करा."
    if status == "Normal":
        return f"{base} तुमचा निकाल {value}{unit_str} आहे, जो तुमच्या अहवालावर दिलेल्या संदर्भ श्रेणीमध्ये{ref_str} आहे.{suffix}"
    if status == "Low":
        return f"{base} तुमचा निकाल {value}{unit_str} आहे, जो तुमच्या अहवालावर दिलेल्या संदर्भ श्रेणीपेक्षा{ref_str} कमी आहे.{suffix}"
    if status == "High":
        return f"{base} तुमचा निकाल {value}{unit_str} आहे, जो तुमच्या अहवालावर दिलेल्या संदर्भ श्रेणीपेक्षा{ref_str} जास्त आहे.{suffix}"
    return (
        f"{base} तुमचा निकाल {value}{unit_str} आहे. "
        "आम्ही तुमच्या अहवालातून या चाचणीची संदर्भ श्रेणी विश्वसनीयपणे वाचू शकलो नाही. "
        "कृपया पात्र वैद्यकीय तज्ञांकडून याची तपासणी करा."
    )
