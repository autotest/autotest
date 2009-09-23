package autotest.tko;

import autotest.common.ui.MultiListSelectPresenter.Item;

import com.google.gwt.json.client.JSONObject;

import java.util.Map;

/**
 * A database field which the user may select for display or filter on.  HeaderFields may generate
 * arbitrary SQL to perform filtering, and they may add arbitrary query arguments to support display
 * and filtering.
 */
abstract class HeaderField implements Comparable<HeaderField> {
    protected String name;
    protected String sqlName;

    /**
     * @param name Display name for this field (i.e. "Job name")
     * @param sqlName SQL field name (i.e. "job_name")
     */
    protected HeaderField(String name, String sqlName) {
        this.name = name;
        this.sqlName = sqlName;
    }
    
    public int compareTo(HeaderField other) {
        return name.compareTo(other.name);
    }

    /**
     * Get the SQL WHERE clause to filter on the given value for this header.
     */
    public abstract String getSqlCondition(String value);

    /**
     * Get the name of this field.
     */
    public String getName() {
        return name;
    }

    /**
     * Get the name to use for this field in a SQL select.
     */
    public String getSqlName() {
        return sqlName;
    }

    /**
     * Get the attribute name of this field on a result object.  This should always be the same as 
     * sqlName, but due to some current flaws in the design, it's necessary as a separate item.
     * TODO: Get rid of this and fix up the design.
     */
    public String getAttributeName() {
        return getSqlName();
    }

    @Override
    public String toString() {
        return "HeaderField<" + getName() + ", " + getSqlName() + ">";
    }
    
    /**
     * @return a MultiListSelectPresenter.Item for this HeaderField.
     */
    public Item getItem() {
        return Item.createItem(getName(), getSqlName());
    }

    /**
     * Add necessary parameters to an RPC request to select this field.  Does nothing by default.
     * @param parameters query parameters
     */
    public void addQueryParameters(JSONObject parameters) {}

    /**
     * Add necessary parameters to history state.  Does nothing by default.
     * @param arguments history arguments
     */
    public void addHistoryArguments(Map<String, String> arguments) {}

    /**
     * Parse information as necessary from history state.
     * @param arguments history arguments
     */
    public void handleHistoryArguments(Map<String, String> arguments) {} 
}
