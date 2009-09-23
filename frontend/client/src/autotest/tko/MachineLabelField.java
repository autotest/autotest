package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class MachineLabelField extends ParameterizedField {
    public static final String BASE_NAME = "Machine labels";
    private static final String MACHINE_LABEL_HEADERS = "machine_label_headers";

    private List<String> labels = new ArrayList<String>();

    @Override
    public String getSqlCondition(String value) {
        List<String> conditionParts = new ArrayList<String>();
        Set<String> selectedLabels = new HashSet<String>(Utils.splitList(value));
        
        for (String label : labels) {
            String condition = "FIND_IN_SET('" + label + "', test_attributes_host_labels.value)";
            if (!selectedLabels.contains(label)) {
                condition = "NOT " + condition;
            }
            conditionParts.add(condition);
        }
        
        return Utils.joinStrings(" AND ", conditionParts);
    }

    @Override
    public void addQueryParameters(JSONObject parameters) {
        JSONObject machineLabelHeaders = 
            Utils.setDefaultValue(parameters, MACHINE_LABEL_HEADERS, new JSONObject()).isObject();
        machineLabelHeaders.put(getSqlName(), Utils.stringsToJSON(labels));
    }

    @Override
    public String getValue() {
        return Utils.joinStrings(",", labels);
    }

    @Override
    public void setValue(String value) {
        labels = Utils.splitListWithSpaces(value);
    }

    @Override
    public String getBaseSqlName() {
        return "machine_labels_";
    }

    @Override
    protected String getBaseName() {
        return BASE_NAME;
    }

    @Override
    protected ParameterizedField freshInstance() {
        return new MachineLabelField();
    }
}
