package autotest.afe;

import autotest.common.table.DataSource;
import autotest.common.table.DynamicTable;
import autotest.common.ui.NotifyManager;

import java.util.ArrayList;
import java.util.Arrays;

public class SelectableProfileStaticHostTable extends SelectableHostTable {
    protected static final String[][] HOST_COLUMNS_SELECT_PROFILE;
    protected static final int profileColumn = HOST_COLUMNS_SELECT.length;
    
    static {
        ArrayList<String[]> list = new ArrayList<String[]>(Arrays.asList(HOST_COLUMNS_SELECT));
        list.add(new String[] {"current_profile", "Current Profile"});
        HOST_COLUMNS_SELECT_PROFILE = list.toArray(new String[0][0]);
    }

    public SelectableProfileStaticHostTable(DataSource dataSource) {
        super(HOST_COLUMNS_SELECT_PROFILE, dataSource);
    }

    protected boolean isProfileColumn(int column) {
        return false;
    }
    
    @Override
    protected void onCellClicked(int row, int cell, boolean isRightClick) {
        if (row == headerRow && cell == profileColumn) { 
            // prevent sorting error on derived columns
            NotifyManager.getInstance().showMessage("Sorting is not supported for this column.");
            return;
        }
        super.onCellClicked(row, cell, isRightClick);
    }

}
