package autotest.afe;

import autotest.common.table.DataSource;
import autotest.common.table.DynamicTable;
import autotest.common.ui.NotifyManager;

import java.util.ArrayList;
import java.util.Arrays;

public class ProfileSelectHostTable extends HostTable {
    protected static final String[][] HOST_COLUMNS_PROFILE;
    protected static int profileColumn;

    static {
        ArrayList<String[]> list = new ArrayList<String[]>(Arrays.asList(HOST_COLUMNS));
        profileColumn = HOST_COLUMNS.length;
        list.add(new String[] {"current_profile", "Selected Profile"});
        HOST_COLUMNS_PROFILE = list.toArray(new String[0][0]);
    }

    public ProfileSelectHostTable(DataSource dataSource) {
        super(HOST_COLUMNS_PROFILE, dataSource);
    }
    
    @Override
    protected void onCellClicked(int row, int cell, boolean isRightClick) {
        if (row == headerRow && cell == profileColumn ) { 
            // prevent sorting error on derived columns
            NotifyManager.getInstance().showMessage("Sorting is not supported for this column.");
            return;
        }
        super.onCellClicked(row, cell, isRightClick);
    }

}
