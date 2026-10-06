/*
 * classify.c
 * -----------------------------------------------------------------------
 * MediExplain AI — native classification helper.
 *
 * Takes a report's numeric value and its printed reference range and
 * decides Low / Normal / High / UNCERTAIN. This is deliberately written
 * in plain C (no floating point surprises, no dependency on any AI
 * model) because this single decision is the one place in the whole
 * pipeline where correctness matters most and must be fully explainable.
 *
 * Usage (called by modules/analysis.py via subprocess):
 *   ./classify <value> <ref_low> <ref_high>
 *   ./classify 9.5 12 15        -> prints: LOW 2.500000 12.000000
 *   ./classify 13.2 12 15       -> prints: NORMAL 0.000000 0.000000
 *   ./classify 9.5 nan nan      -> prints: UNCERTAIN 0.000000 0.000000
 *
 * Output line: "<STATUS> <distance_from_range> <percent_of_low_bound>"
 * distance_from_range is 0 for NORMAL/UNCERTAIN, otherwise how far
 * outside the printed range the value sits (same units as the report),
 * which the UI uses to show "slightly low" vs "very low".
 *
 * Build: gcc -O2 -Wall -o classify classify.c
 * -----------------------------------------------------------------------
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <math.h>

typedef enum { STATUS_LOW, STATUS_NORMAL, STATUS_HIGH, STATUS_UNCERTAIN } status_t;

static const char *status_name(status_t s) {
    switch (s) {
        case STATUS_LOW: return "LOW";
        case STATUS_HIGH: return "HIGH";
        case STATUS_NORMAL: return "NORMAL";
        default: return "UNCERTAIN";
    }
}

/* Parses a token as a double. Returns 1 on success, 0 if it is not a
 * usable number (e.g. the string "nan", "null", "" or garbage OCR
 * text) — in which case we must NEVER guess, only report UNCERTAIN. */
static int parse_double_strict(const char *s, double *out) {
    if (s == NULL || s[0] == '\0') return 0;
    if (strcasecmp(s, "nan") == 0 || strcasecmp(s, "null") == 0 ||
        strcasecmp(s, "none") == 0 || strcasecmp(s, "na") == 0) {
        return 0;
    }
    char *end = NULL;
    *out = strtod(s, &end);
    if (end == s) return 0;          /* nothing parsed              */
    while (*end == ' ') end++;       /* tolerate trailing whitespace */
    if (*end != '\0') return 0;      /* trailing junk -> not a clean number */
    if (isnan(*out) || isinf(*out)) return 0;
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s <value> <ref_low> <ref_high>\n", argv[0]);
        return 2;
    }

    double value, low, high;
    int have_value = parse_double_strict(argv[1], &value);
    int have_low   = parse_double_strict(argv[2], &low);
    int have_high  = parse_double_strict(argv[3], &high);

    if (!have_value || !have_low || !have_high || low > high) {
        /* Rule from the spec: if the range is missing or ambiguous,
         * mark 'Unable to determine' instead of guessing. */
        printf("%s 0.000000 0.000000\n", status_name(STATUS_UNCERTAIN));
        return 0;
    }

    status_t status;
    double distance = 0.0;

    if (value < low) {
        status = STATUS_LOW;
        distance = low - value;
    } else if (value > high) {
        status = STATUS_HIGH;
        distance = value - high;
    } else {
        status = STATUS_NORMAL;
        distance = 0.0;
    }

    /* percent_of_low_bound helps the UI phrase severity ("~20% below
     * the lower bound") without doing any medical interpretation. */
    double percent = 0.0;
    if (status != STATUS_NORMAL && low != 0.0) {
        percent = (distance / low) * 100.0;
    }

    printf("%s %f %f\n", status_name(status), distance, percent);
    return 0;
}
