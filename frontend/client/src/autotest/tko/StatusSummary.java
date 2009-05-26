// Copyright 2008 Google Inc. All Rights Reserved.

package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.Arrays;

class StatusSummary {
    static final String BLANK_COLOR = "#FFFFFF";
    static final ColorMapping[] CELL_COLOR_MAP = {
        // must be in descending order of percentage
        new ColorMapping(95, "#32CD32"),
        new ColorMapping(90, "#c0ff80"),
        new ColorMapping(85, "#ffff00"),
        new ColorMapping(75, "#ffc040"),
        new ColorMapping(1, "#ff4040"),
        new ColorMapping(0, "#d080d0"),
    };
    
    public int passed = 0;
    public int complete = 0;
    public int incomplete = 0;
    public int total = 0; // TEST_NA is included here, but not in any other
    
    private String[] contents = null;
    
    /**
     * Stores a color for pass rates and the minimum passing percentage required
     * to have that color.
     */
    static class ColorMapping {
        // store percentage as int so we can reprint it consistently
        public int minPercent;
        public String htmlColor;
        
        public ColorMapping(int minPercent, String htmlColor) {
            this.minPercent = minPercent;
            this.htmlColor = htmlColor;
        }
        
        public boolean matches(double ratio) {
            return ratio * 100 >= minPercent;
        }
    }
    
    public static StatusSummary getStatusSummary(JSONObject group) {
        StatusSummary summary = new StatusSummary();
        summary.passed = getField(group, TestGroupDataSource.PASS_COUNT_FIELD);
        summary.complete = getField(group, TestGroupDataSource.COMPLETE_COUNT_FIELD);
        summary.incomplete = getField(group, TestGroupDataSource.INCOMPLETE_COUNT_FIELD);
        summary.total = getField(group, TestGroupDataSource.GROUP_COUNT_FIELD);
        
        if (group.containsKey("extra_info")) {
            summary.contents = Utils.JSONtoStrings(group.get("extra_info").isArray());
        }
        
        return summary;
    }

    private static int getField(JSONObject group, String field) {
        return (int) group.get(field).isNumber().doubleValue();
    }
    
    /**
     * Force construction to go through getStatusSummary() factory method.
     */
    private StatusSummary() {}
    
    public int getTotal() {
        return total;
    }

    public String formatContents() {
        String result = formatStatusCounts();
        
        if (contents != null) {
            result += "<br>";
            result += Utils.joinStrings("<br>", Arrays.asList(contents), true);
        }
        
        return result;
    }
    
    private String formatStatusCounts() {
        String text = passed + " / " + complete;
        if (incomplete > 0) {
            text += " (" + incomplete + " incomplete)";
        }
        return text;
    }

    public String getColor() {
        if (complete == 0) {
            return BLANK_COLOR;
        }
        double ratio = (double) passed / complete;
        for (ColorMapping mapping : CELL_COLOR_MAP) {
            if (mapping.matches(ratio))
                return mapping.htmlColor;
        }
        throw new RuntimeException("No color map match for ratio " + ratio);
    }
}