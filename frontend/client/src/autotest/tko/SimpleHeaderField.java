package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

class SimpleHeaderField extends HeaderField {
    public SimpleHeaderField(String name, String sqlName) {
        super(name, sqlName);
    }

    @Override
    public String getSqlCondition(String value) {
        if (value.equals(Utils.JSON_NULL)) {
          return getSqlName() + " is null";
        } else {
          return getSqlName() + " = '" + TkoUtils.escapeSqlValue(value) + "'";
        }
    }

    @Override
    public void addQueryParameters(JSONObject parameters) {
        // don't need to add anything
    }
}
