package autotest.common.ui;

import com.google.gwt.user.client.ui.ListBox;

public class ExtendedListBox extends ListBox implements SimplifiedList {
    private int findItemByName(String name) {
        for (int i = 0; i < getItemCount(); i++) {
            if (getItemText(i).equals(name)) {
                return i;
            }
        }
        throw new IllegalArgumentException("No such name found: " + name);
    }
    
    private int findItemByValue(String value) {
        for (int i = 0; i < getItemCount(); i++) {
            if (getValue(i).equals(value)) {
                return i;
            }
        }
        throw new IllegalArgumentException("No such value found: " + value);
    }

    public void removeItemByName(String name) {
        removeItem(findItemByName(name));
    }
    
    private boolean isNothingSelected() {
        return getSelectedIndex() == -1;
    }
    
    public String getSelectedName() {
        if (isNothingSelected()) {
            return null;
        }
        return getItemText(getSelectedIndex());
    }

    public String getSelectedValue() {
        if (isNothingSelected()) {
            return null;
        }
        return getValue(getSelectedIndex());
    }

    public void selectByName(String name) {
        setSelectedIndex(findItemByName(name));
    }

    public void selectByValue(String value) {
        setSelectedIndex(findItemByValue(value));
    }
}
