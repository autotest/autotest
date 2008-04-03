package afeclient.client.table;

import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Widget;

public class ListFilter extends FieldFilter {
    protected ListBox select = new ListBox();
    protected String allValuesText = "All values";
    
    public ListFilter(String fieldName) {
        super(fieldName);
        select.setStylePrimaryName("filter-box");
        select.addChangeListener(new ChangeListener() {
            public void onChange(Widget sender) {
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
    
    public void setExactMatch(boolean isExactMatch) {
        this.isExactMatch = isExactMatch;
    }

    public String getMatchValue() {
        return select.getItemText(select.getSelectedIndex()); 
    }
    
    public boolean isActive() {
        return !getMatchValue().equals(allValuesText);
    }
    
    public Widget getWidget() {
        return select;
    }

    public void setChoices(String[] choices) {
        String selectedValue = null;
        if (select.getSelectedIndex() != -1)
            selectedValue = getMatchValue();
        
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