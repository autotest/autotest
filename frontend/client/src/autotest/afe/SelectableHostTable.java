package autotest.afe;

import autotest.common.table.DataSource;
import autotest.common.ui.NotifyManager;

import java.util.ArrayList;
import java.util.Arrays;

public class SelectableHostTable extends HostTable {
    protected static final String[][] HOST_COLUMNS_SELECT;
    private final int PLATFORM_COLUMN = 2;
    private final int LABELS_COLUMN = 3;

    static {
        ArrayList<String[]> list = new ArrayList<String[]>(Arrays.asList(HOST_COLUMNS));
        list.add(0, new String[] {CLICKABLE_WIDGET_COLUMN, "Select"});
        HOST_COLUMNS_SELECT = list.toArray(new String[0][0]);
    }

    public SelectableHostTable(DataSource dataSource) {
        super(HOST_COLUMNS_SELECT, dataSource);
    }

    public SelectableHostTable(String[][] columns, DataSource dataSource) {
        super(columns, dataSource);
    }
    
    @Override
    protected void onCellClicked(int row, int cell, boolean isRightClick) {
        if (row == headerRow && (cell == PLATFORM_COLUMN || cell == LABELS_COLUMN) ) { 
            // prevent sorting error on derived columns
            NotifyManager.getInstance().showMessage("Sorting is not supported for this column.");
            return;
        }
        super.onCellClicked(row, cell, isRightClick);
    }
}
