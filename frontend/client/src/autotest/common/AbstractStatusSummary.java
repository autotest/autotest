package autotest.common;


public abstract class AbstractStatusSummary {
    public static final String BLANK_COLOR = "status_blank";
    private static final ColorMapping[] CELL_COLOR_MAP = {
        // must be in descending order of percentage
        new ColorMapping(95, "status_95"),
        new ColorMapping(90, "status_90"),
        new ColorMapping(85, "status_85"),
        new ColorMapping(75, "status_75"),
        new ColorMapping(1, "status_bad"),
        new ColorMapping(0, "status_none"),
    };

    /**
     * Stores a CSS class for pass rates and the minimum passing percentage required
     * to have that class.
     */
    private static class ColorMapping {
        // store percentage as int so we can reprint it consistently
        public int minPercent;
        public String cssClass;

        public ColorMapping(int minPercent, String cssClass) {
            this.minPercent = minPercent;
            this.cssClass = cssClass;
        }

        public boolean matches(double ratio) {
            return ratio * 100 >= minPercent;
        }
    }

    public String formatStatusCounts() {
        String text = getPassed() + " / " + getComplete();
        if (getIncomplete() > 0) {
            text += " (" + getIncomplete() + " incomplete)";
        }
        return text;
    }

    public String getCssClass() {
        if (getComplete() == 0) {
            return BLANK_COLOR;
        }
        double ratio = (double) getPassed() / getComplete();
        for (ColorMapping mapping : CELL_COLOR_MAP) {
            if (mapping.matches(ratio))
                return mapping.cssClass;
        }
        throw new RuntimeException("No color map match for ratio " + ratio);
    }

    protected abstract int getPassed();
    protected abstract int getComplete();
    protected abstract int getIncomplete();
}
