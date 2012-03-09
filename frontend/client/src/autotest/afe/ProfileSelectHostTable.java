package autotest.afe;

import autotest.common.table.DataSource;
import autotest.common.table.DynamicTable;

import java.util.ArrayList;
import java.util.Arrays;

public class ProfileSelectHostTable extends HostTable {
    private static final String[][] HOST_COLUMNS_PROFILE;

    static {
        ArrayList<String[]> list = new ArrayList<String[]>(Arrays.asList(HOST_COLUMNS));
        list.add(new String[] {"current_profile", "Selected Profile"});
        HOST_COLUMNS_PROFILE = list.toArray(new String[0][0]);
    }
    
    public ProfileSelectHostTable(DataSource dataSource) {
        super(HOST_COLUMNS_PROFILE, dataSource);
    }
}
