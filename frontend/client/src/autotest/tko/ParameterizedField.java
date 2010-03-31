package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;

public abstract class ParameterizedField extends HeaderField {
    private static class FieldIdentifier {
        String type;
        String value;
        
        public FieldIdentifier(ParameterizedField field) {
            this.type = field.getTypeName();
            this.value = field.getValue();
        }
    
        @Override
        public int hashCode() {
            return type.hashCode() + 31 * value.hashCode();
        }
    
        @Override
        public boolean equals(Object obj) {
            if (obj == null || !(obj instanceof FieldIdentifier)) {
                return false;
            }
    
            FieldIdentifier other = (FieldIdentifier) obj;
            return type.equals(other.type) && value.equals(other.value);
        }
    }

    private static final ParameterizedField[] prototypes = new ParameterizedField[] {
        // add all ParameterizedField subclasses here.  these instances should never escape. 
        new MachineLabelField(),
        new IterationResultField(),
        new TestAttributeField(),
        new TestLabelField(),
        new JobKeyvalField(),
        new IterationAttributeField(),
    };
    
    private static final List<String> prototypeNames = new ArrayList<String>();
    static {
        for (ParameterizedField prototype : prototypes) {
            prototypeNames.add(prototype.getTypeName());
        }
    }

    private String value;

    protected ParameterizedField() {
        super("", "");
    }

    public static ParameterizedField newInstance(String typeName, String value) {
        ParameterizedField prototype = getPrototype(typeName);
        ParameterizedField newField = prototype.freshInstance();
        newField.setValue(value);
        return newField;
    }

    public static Collection<String> getFieldTypeNames() {
        return Collections.unmodifiableCollection(prototypeNames);
    }

    private static ParameterizedField getPrototype(String name) {
        for (ParameterizedField prototype : prototypes) {
            if (name.startsWith(prototype.getTypeName())) {
                return prototype;
            }
        }

        throw new IllegalArgumentException("No prototype found for " + name);
    }
    
    @Override
    public String getSqlName() {
        return getBaseSqlName() + getValue();
    }

    @Override
    public void addQueryParameters(JSONObject parameters) {
        JSONArray fieldValueList = 
            Utils.setDefaultValue(parameters, getFieldParameterName(), new JSONArray()).isArray();
        fieldValueList.set(fieldValueList.size(), new JSONString(getValue()));
    }

    /**
     * @return the prefix of the SQL name generated for each field
     */
    protected abstract String getBaseSqlName();

    /**
     * @return name of the parameter to pass with a list of field names for this field type
     */
    protected abstract String getFieldParameterName();

    /**
     * @return a string identifying this type of field
     */
    public abstract String getTypeName();

    /**
     * @return a new instance of the subclass type.
     */
    protected abstract ParameterizedField freshInstance();

    @Override
    public String getName() {
        return getTypeName() + ": " + getValue();
    }

    public String getValue() {
        return value;
    }

    public void setValue(String value) {
        this.value = value;
    }
    
    public Object getIdentifier() {
        return new FieldIdentifier(this);
    }
    
    /**
     * Get the exact field to use in a SQL WHERE clause to filter on this field.
     * 
     * This is a necessary artifact of the way we directly expose SQL WHERE clauses to the user.  It
     * will hopefully be possible to get rid of this in the future if that changes.
     */
    public abstract String getFilteringName();
}
