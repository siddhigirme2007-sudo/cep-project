// parse_lines.cpp
// ---------------------------------------------------------------------
// MediExplain AI — native OCR line-parsing helper.
//
// Tesseract/EasyOCR hand back a wall of loosely-aligned text. This
// tool scans that raw text line by line and pulls out the lines that
// *look like* a lab-test row: a name, followed by a number, optionally
// a unit, optionally a printed reference range such as "12-15" or
// "12 - 15 g/dL". It does no medical interpretation at all — it only
// finds candidate rows and hands them to modules/extraction.py as
// tab-separated fields for the Python layer to finish structuring.
//
// Written in C++ (not Python) because this scan runs over every line
// of every uploaded report and benefits from being fast, and because
// the assignment calls for a genuinely polyglot stack.
//
// Usage:
//   ./parse_lines < ocr_raw_text.txt
//   (reads stdin, writes one TSV line per candidate row to stdout:
//    name<TAB>value<TAB>unit<TAB>ref_low<TAB>ref_high<TAB>ref_text)
//
// Build: g++ -O2 -std=c++17 -Wall -o parse_lines parse_lines.cpp
// ---------------------------------------------------------------------

#include <iostream>
#include <sstream>
#include <string>
#include <regex>
#include <vector>
#include <algorithm>
#include <cctype>

namespace {

std::string trim(const std::string &s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

// Collapses runs of whitespace so OCR's inconsistent spacing doesn't
// break downstream regex matching.
std::string normalize_spaces(const std::string &s) {
    std::string out;
    bool last_space = false;
    for (char c : s) {
        bool is_space = std::isspace(static_cast<unsigned char>(c));
        if (is_space) {
            if (!last_space) out += ' ';
            last_space = true;
        } else {
            out += c;
            last_space = false;
        }
    }
    return trim(out);
}

// A very small set of known lab units. Not exhaustive on purpose —
// unknown units are still captured as free text, extraction.py can
// widen this list without touching the parser's control flow.
const std::vector<std::string> KNOWN_UNITS = {
    "g/dL", "g/dl", "mg/dL", "mg/dl", "mmol/L", "mmol/l", "IU/L", "IU/l",
    "U/L", "u/l", "%", "cells/cumm", "million/cumm", "/cumm", "ng/mL",
    "ng/ml", "pg", "fL", "fl", "mIU/mL", "miu/ml", "µg/dL", "ug/dL"
};

} // namespace

int main() {
    // A candidate row looks like:
    //   <name text>  <value>  [unit]  [ (low - high) | low-high | low – high ]
    // Example OCR lines this must survive:
    //   "Hemoglobin        9.5 g/dL      12 - 15"
    //   "Hemoglobin (Hb)  9.5  g/dL   Ref: 12-15 g/dL"
    //   "WBC Count   11200   cells/cumm   4000-11000"
    static const std::regex row_pattern(
        R"(^(.*?[A-Za-z][A-Za-z\)\]\.\s]*?)\s+(-?\d+(?:\.\d+)?)\s*([A-Za-zµ/%]*)\s*[:\-]?\s*(?:\(?\s*Ref\.?:?\s*)?(-?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(-?\d+(?:\.\d+)?)\s*\)?\s*([A-Za-zµ/%]*)\s*$)",
        std::regex::icase
    );

    std::string raw_line;
    while (std::getline(std::cin, raw_line)) {
        std::string line = normalize_spaces(raw_line);
        if (line.empty() || line.size() < 4) continue;

        std::smatch m;
        if (!std::regex_match(line, m, row_pattern)) continue;

        std::string name      = trim(m[1].str());
        std::string value_s   = trim(m[2].str());
        std::string unit_a    = trim(m[3].str());
        std::string low_s     = trim(m[4].str());
        std::string high_s    = trim(m[5].str());
        std::string unit_b    = trim(m[6].str());

        if (name.empty()) continue;

        std::string unit = !unit_a.empty() ? unit_a : unit_b;

        // Sanity check: a real range has low <= high. If OCR mangled
        // it so badly that low > high, don't fabricate a fix — report
        // the row with an empty range so the Python/C layer marks it
        // 'Unable to determine' rather than guessing.
        try {
            double low_v = std::stod(low_s);
            double high_v = std::stod(high_s);
            if (low_v > high_v) {
                low_s.clear();
                high_s.clear();
            }
        } catch (...) {
            low_s.clear();
            high_s.clear();
        }

        std::cout << name << '\t' << value_s << '\t' << unit << '\t'
                   << low_s << '\t' << high_s << '\t'
                   << (low_s.empty() ? "" : (low_s + "-" + high_s))
                   << '\n';
    }

    return 0;
}
