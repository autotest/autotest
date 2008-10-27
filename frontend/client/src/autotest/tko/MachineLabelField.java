package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class MachineLabelField extends HeaderField {
    private static final String MACHINE_LABEL_HEADERS = "machine_label_headers";
    private static final String BASE_NAME = "Machine labels ";
    public static final String BASE_SQL_NAME = "machine_labels_";
    
    private static int nameCounter = 0;
    
    private List<String> labels = new ArrayList<String>();

    public static MachineLabelField newInstance() {
        String numberString = Integer.toString(nameCounter);
        nameCounter++;

        return new MachineLabelField(numberString);
    }
    
    public static MachineLabelField fromFieldName(String fieldName) {
        assert fieldName.startsWith(BASE_SQL_NAME);
        String numberString = fieldName.substring(BASE_SQL_NAME.length());
        int number;
        try {
            number = Integer.valueOf(numberString);
        } catch (NumberFormatException exc) {
            throw new IllegalArgumentException("Failed to parse header " + fieldName);
        }

        // ensure name counter never overlaps this field name
        if (nameCounter <= number) {
            nameCounter = number + 1;
        }
        
        return new MachineLabelField(numberString);
    }

    private MachineLabelField(String numberString) {
        super(BASE_NAME + numberString, BASE_SQL_NAME + numberString);
    }

    public void setLabels(List<String> labels) {
        this.labels = labels;
    }
    
    public List<String> getLabelList() {
        return Collections.unmodifiableList(labels);
    }

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
}
