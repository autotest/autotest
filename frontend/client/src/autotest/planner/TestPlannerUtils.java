package autotest.planner;

import com.google.gwt.gen2.table.client.FixedWidthFlexTable;
import com.google.gwt.gen2.table.client.FixedWidthGrid;
import com.google.gwt.gen2.table.client.ScrollTable;

public class TestPlannerUtils {

    private static final int HEIGHT_FUDGE = 300;

    public static String getHeightParam(int windowHeight) {
        return (windowHeight - HEIGHT_FUDGE) + "px";
    }

    public static void resizeScrollTable(ScrollTable scrollTable) {
        resizeScrollTable(scrollTable, false);
    }

    public static void resizeScrollTable(ScrollTable scrollTable, boolean hasSelectAllHeader) {
        FixedWidthGrid dataTable = scrollTable.getDataTable();
        FixedWidthFlexTable header = scrollTable.getHeaderTable();

        for (int column = 0; column < dataTable.getColumnCount(); column++) {
            int headerColumn = column;
            if (hasSelectAllHeader) {
                headerColumn++;
            }

            int width = Math.max(
                      dataTable.getIdealColumnWidth(column),
                      header.getIdealColumnWidth(headerColumn));

            header.setColumnWidth(headerColumn, width);
            dataTable.setColumnWidth(column, width);
        }
    }
}
