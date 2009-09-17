package autotest.common.table;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Widget;

public class ListFilter extends FieldFilter {
    protected ListBox select = new ListBox();
    protected String allValuesText = "All values";
    
    public ListFilter(String fieldName) {
        super(fieldName);
        select.setStylePrimaryName("filter-box");
        select.addChangeHandler(new ChangeHandler() {
            public void onChange(ChangeEvent event) {
                notifyListeners();
            } 
        });
    }
    
    /**
     * Set the text for that option that matches any value for this filter.
     */
    public void setMatchAllText(String text) {
        allValuesText = text;
        if (select.getItemCount() > 0)
            select.setItemText(0, allValuesText);
    }
    
    @Override
    public void setExactMatch(boolean isExactMatch) {
        this.isExactMatch = isExactMatch;
    }
    
    protected String getItemText(int index) {
        return select.getItemText(index);
    }
    
    protected String getSelectedText() {
        int selected = select.getSelectedIndex();
        if (selected == -1)
            return "";
        return getItemText(selected);
    }

    @Override
    public JSONValue getMatchValue() {
        return new JSONString(getSelectedText()); 
    }
    
    @Override
    public boolean isActive() {
        return !getSelectedText().equals(allValuesText);
    }
    
    @Override
    public Widget getWidget() {
        return select;
    }

    public void setChoices(String[] choices) {
        String selectedValue = null;
        if (select.getSelectedIndex() != -1)
            selectedValue = getSelectedText();
        
        select.clear();
        select.addItem(allValuesText);
        for (int i = 0; i < choices.length; i++)
            select.addItem(choices[i]);
        
        if (selectedValue != null) {
            setSelectedChoice(selectedValue);
        }
    }
    
    public void setSelectedChoice(String choice) {
        for(int i = 0; i < select.getItemCount(); i++) {
            if(select.getItemText(i).equals(choice)) {
                select.setSelectedIndex(i);
                return;
            }
        }
        
        select.addItem(choice);
        select.setSelectedIndex(select.getItemCount() - 1);
    }
}