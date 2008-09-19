package autotest.tko;

import autotest.common.StaticDataRepository;
import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;

public class DBColumnSelector extends Composite {
    
    public static final String PERF_VIEW = "perf_view";
    public static final String TEST_VIEW = "test_view";
    
    private ListBox field = new ListBox();
    private ArrayList<ChangeListener> listeners = new ArrayList<ChangeListener>();
    
    public DBColumnSelector(String view) {
        this(view, false);
    }
    
    public DBColumnSelector(String view, boolean canUseSinglePoint) {
        if (canUseSinglePoint) {
            field.addItem("(Single Point)", "'data'");
        }
      
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray fields = staticData.getData(view).isArray();
        for (int i = 0; i < fields.size(); i++) {
            JSONArray perfField = fields.get(i).isArray();
            String fieldName = Utils.jsonToString(perfField.get(0));
            String column = Utils.jsonToString(perfField.get(1));
            field.addItem(fieldName, column);
        }
        
        field.addChangeListener(new ChangeListener() {
            public void onChange(Widget w) {
                notifyListeners();
            }
        });

        initWidget(field);
    }
    
    public void addChangeListener(ChangeListener listener) {
        listeners.add(listener);
    }
    
    public String getColumn() {
        return field.getValue(field.getSelectedIndex());
    }
    
    public void setEnabled(boolean enabled) {
        field.setEnabled(enabled);
    }
    
    // Select the value in the drop-down whose column name matches the given parameter
    public void selectColumn(String column) {
        for (int i = 0; i < field.getItemCount(); i++) {
            if (field.getValue(i).equals(column)) {
                field.setSelectedIndex(i);
                break;
            }
        }
    }
    
    public void setSelectedIndex(int index) {
        field.setSelectedIndex(index);
    }
    
    private void notifyListeners() {
        for (ChangeListener listener : listeners) {
            listener.onChange(this);
        }
    }
}
