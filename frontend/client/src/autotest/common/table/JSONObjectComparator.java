package autotest.common.table;

import autotest.common.table.DataSource.SortSpec;

import com.google.gwt.json.client.JSONObject;

import java.util.Comparator;

public class JSONObjectComparator implements Comparator<JSONObject> {
    SortSpec[] sortSpecs;
    
    public JSONObjectComparator(SortSpec[] specs) {
        sortSpecs = specs;
    }

    public int compare(JSONObject arg0, JSONObject arg1) {
        int compareValue = 0;
        for (SortSpec sortSpec : sortSpecs) {
            String key0 = arg0.get(sortSpec.getField()).toString().toLowerCase();
            String key1 = arg1.get(sortSpec.getField()).toString().toLowerCase();
            compareValue = key0.compareTo(key1) * sortSpec.getDirectionMultiplier();
            if (compareValue != 0) {
                break;
            }
        }
        return compareValue;
    }
}