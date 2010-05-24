package autotest.planner;

import autotest.common.AbstractStatusSummary;

import java.util.Collection;

public interface TestPlannerTableDisplay {

    public static class RowDisplay {
        String content;
        String cssClass = AbstractStatusSummary.BLANK_COLOR;

        public RowDisplay(String content) {
            this.content = content;
        }

        public RowDisplay(String content, String cssClass) {
            this.content = content;
            this.cssClass = cssClass;
        }
    }

    public void addRow(Collection<RowDisplay> rowData);
    public void finalRender();
    public void clearData();
    public void setHeaders(Collection<String> headers);
}
