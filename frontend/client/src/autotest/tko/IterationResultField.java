package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

public class IterationResultField extends ParameterizedField {
    public static final String BASE_NAME = "Iteration result";
    private String attribute;

    @Override
    protected ParameterizedField freshInstance() {
        return new IterationResultField();
    }

    @Override
    protected String getBaseName() {
        return BASE_NAME;
    }

    @Override
    public String getBaseSqlName() {
        return "iteration_result_";
    }

    @Override
    public String getValue() {
        return attribute;
    }

    @Override
    public void setValue(String value) {
        attribute = value;
    }

    @Override
    public String getAttributeName() {
        return getValue();
    }

    @Override
    public void addQueryParameters(JSONObject parameters) {
        JSONArray iterationKeys = 
            Utils.setDefaultValue(parameters, "result_keys", new JSONArray()).isArray();
        iterationKeys.set(iterationKeys.size(), new JSONString(attribute));
    }

    @Override
    public String getSqlCondition(String value) {
        // TODO: when grouping on iteration results is added, this will be necessary
        throw new UnsupportedOperationException();
    }

}
