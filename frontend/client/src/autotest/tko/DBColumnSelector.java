package autotest.tko;

import autotest.common.ui.ExtendedListBox;
import autotest.tko.TkoUtils.FieldInfo;


public class DBColumnSelector extends ExtendedListBox {
    public static final String PERF_VIEW = "tko_perf_view";
    public static final String TEST_VIEW = "tko_test_view";

    public DBColumnSelector(String view) {
        this(view, false);
    }

    public DBColumnSelector(String view, boolean canUseSinglePoint) {
        if (canUseSinglePoint) {
            addItem("(Single Point)", "'data'");
        }
        
        for (FieldInfo fieldInfo : TkoUtils.getFieldList(view)) {
            addItem(fieldInfo.name, fieldInfo.field);
        }
    }
}
