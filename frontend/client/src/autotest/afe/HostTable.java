package autotest.afe;

import autotest.common.table.DataSource;
import autotest.common.table.DynamicTable;

import java.util.ArrayList;
import java.util.Arrays;

public class HostTable extends DynamicTable {
    protected static final String[][] HOST_COLUMNS = {
        {"hostname", "Hostname"}, {"platform", "Platform"}, 
        {HostDataSource.OTHER_LABELS, "Other labels"}, {"status", "Status"}, 
        {HostDataSource.LOCKED_TEXT, "Locked"},
    };
    
    public HostTable(DataSource dataSource) {
        super(HOST_COLUMNS, dataSource);
    }

    public HostTable(String[][] columns, DataSource dataSource) {
        super(columns, dataSource);
    }
}
