package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

public class TestAttributeField extends StringParameterizedField {
    public static final String BASE_NAME = "Test attribute";

    @Override
    protected ParameterizedField freshInstance() {
        return new TestAttributeField();
    }

    @Override
    protected String getBaseName() {
        return BASE_NAME;
    }

    @Override
    public String getBaseSqlName() {
        return "attribute_";
    }

    @Override
    public String getAttributeName() {
        return "attribute_" + getValue();
    }

    @Override
    public void addQueryParameters(JSONObject parameters) {
        JSONArray testAttributes = 
            Utils.setDefaultValue(parameters, "test_attributes", new JSONArray()).isArray();
        testAttributes.set(testAttributes.size(), new JSONString(getValue()));
    }

    @Override
    public String getSqlCondition(String value) {
        return getSimpleSqlCondition(getAttributeName(), value);
    }

}
