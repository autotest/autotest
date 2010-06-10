package autotest.tko;

import autotest.common.spreadsheet.Spreadsheet.CellInfo;
import autotest.common.spreadsheet.Spreadsheet.Header;

import com.google.gwt.json.client.JSONObject;

import java.util.List;

public class TkoSpreadsheetUtils {
    public static enum DrilldownType {DRILLDOWN_ROW, DRILLDOWN_COLUMN, DRILLDOWN_BOTH}

    public static TestSet getTestSet(CellInfo cellInfo, JSONObject condition,
            List<HeaderField> rowFields, List<HeaderField> columnFields) {
        boolean isSingleTest = cellInfo.testCount == 1;
        if (isSingleTest) {
            return new SingleTestSet(cellInfo.testIndex, condition);
        }

        ConditionTestSet testSet = new ConditionTestSet(condition);
        if (cellInfo.row != null) {
            setSomeFields(testSet, rowFields, cellInfo.row);
        }
        if (cellInfo.column != null) {
            setSomeFields(testSet, columnFields, cellInfo.column);
        }
        return testSet;
    }

    private static void setSomeFields(ConditionTestSet testSet, List<HeaderField> allFields,
            Header values) {
        for (int i = 0; i < values.size(); i++) {
            HeaderField field = allFields.get(i);
            String value = values.get(i);
            testSet.addCondition(field.getSqlCondition(value));
        }
    }

    public static DrilldownType getDrilldownType(CellInfo cellInfo) {
        if (cellInfo.row == null) {
            // column header
            return DrilldownType.DRILLDOWN_COLUMN;
        }
        if (cellInfo.column == null) {
            // row header
            return DrilldownType.DRILLDOWN_ROW;
        }
        return DrilldownType.DRILLDOWN_BOTH;
    }
}
