package autotest.common.table;

import autotest.common.table.DataSource.SortSpec;

import com.google.gwt.json.client.JSONObject;

import java.util.Comparator;

public class JSONObjectComparator implements Comparator<JSONObject> {
    SortSpec[] sortSpecs;

    public JSONObjectComparator(SortSpec[] specs) {
        sortSpecs = new SortSpec[specs.length];
        System.arraycopy(specs, 0, sortSpecs, 0, specs.length);
    }

    public int compare(JSONObject arg0, JSONObject arg1) {
        int compareValue = 0;
        for (SortSpec sortSpec : sortSpecs) {
            String key0 = arg0.get(sortSpec.getField()).toString().toLowerCase();
            String key1 = arg1.get(sortSpec.getField()).toString().toLowerCase();
            compareValue = key0.compareTo(key1) * sortSpec.getDirectionMultiplier();
            if (compareValue != 0) {
                return compareValue;
            }
        }

        // the given sort keys were all equal, but we'll ensure we're consistent with
        // JSONObject.equals()
        if (arg0.equals(arg1)) {
            return 0;
        }
        // arbitrary (but consistent) ordering in this case
        return arg0.hashCode() > arg1.hashCode() ? 1 : -1;
    }
}
