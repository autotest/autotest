package autotest.afe;

import autotest.common.table.MultipleListFilter;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Widget;

public class LabelFilter extends MultipleListFilter {
    public static final int VISIBLE_SIZE = 10;
    private final ListBox platform;
    
    public LabelFilter() {
      super("multiple_labels", VISIBLE_SIZE);
      setMatchAllText("All labels");
      setChoices(AfeUtils.getNonPlatformLabelStrings());
      
      String[] platformStrings = AfeUtils.getPlatformStrings();
      
      platform = new ListBox();
      platform.addItem("All platforms");
      for (String platformString : platformStrings) {
        platform.addItem(platformString);
      }
      platform.setStylePrimaryName("filter-box");
      platform.addChangeHandler(new ChangeHandler() {
        public void onChange(ChangeEvent event) {
            notifyListeners();
        }
    });
    }

    @Override
    protected String getItemText(int index) {
        return AfeUtils.decodeLabelName(super.getItemText(index));
    }
    
    public Widget getPlatformWidget() {
        return platform;
    }
    
    @Override
    public JSONValue getMatchValue() {
      JSONArray labels = super.getMatchValue().isArray();

      int selectedIndex = platform.getSelectedIndex();
      // Skip the first item ("All platforms")
      if (selectedIndex > 0) {
        String platformString = platform.getItemText(selectedIndex);
        labels.set(labels.size(), new JSONString(platformString));
      }

      return labels;
  }
}
