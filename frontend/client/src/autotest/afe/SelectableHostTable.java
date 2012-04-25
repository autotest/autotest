package autotest.afe;

import autotest.common.table.DataSource;
import autotest.common.table.DynamicTable;

import java.util.ArrayList;
import java.util.Arrays;

public class SelectableHostTable extends HostTable {
    protected static final String[][] HOST_COLUMNS_SELECT;

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
}
