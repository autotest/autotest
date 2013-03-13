package autotest.afe;

import autotest.common.table.RpcDataSource;

public class ProfileDataSource extends RpcDataSource {
    public ProfileDataSource() {
        super("get_profiles", "get_num_profiles");
    }
}
