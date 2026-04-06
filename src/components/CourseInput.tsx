import React from 'react';
import { useStore } from '../store';
import { Trash2, Plus, RefreshCw, FileText } from 'lucide-react';

export const CourseInput: React.FC = () => {
  const { courses, addCourse, removeCourse, updateCourse, clearCourses, fillExample } = useStore();

  return (
    <div className="bg-white rounded-xl shadow-sm border border-neutral-300 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
        <h2 className="text-2xl font-bold text-neutral-900">成绩输入</h2>
        <div className="flex gap-2">
          <button 
            onClick={fillExample}
            className="flex items-center px-3 py-1.5 text-sm font-medium text-brand-blue bg-brand-blue-light rounded-lg hover:bg-blue-100 transition-colors"
          >
            <FileText className="w-4 h-4 mr-1" />
            填入示例
          </button>
          <button 
            onClick={clearCourses}
            className="flex items-center px-3 py-1.5 text-sm font-medium text-neutral-500 bg-neutral-50 rounded-lg hover:bg-neutral-100 transition-colors"
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            清空
          </button>
        </div>
      </div>

      <div className="hidden sm:grid grid-cols-12 gap-4 mb-3 px-2 text-sm font-semibold text-neutral-500">
        <div className="col-span-5">课程名称</div>
        <div className="col-span-3">学分</div>
        <div className="col-span-3">成绩 (百分制)</div>
        <div className="col-span-1 text-center">操作</div>
      </div>

      <div className="space-y-3 mb-6">
        {courses.map((course, index) => (
          <div key={course.id} className="flex flex-col sm:grid sm:grid-cols-12 gap-3 sm:gap-4 p-4 sm:p-2 bg-neutral-50 sm:bg-transparent rounded-lg sm:rounded-none border sm:border-none border-neutral-200">
            <div className="sm:hidden text-xs font-semibold text-neutral-500 mb-1">课程 {index + 1}</div>
            
            <div className="col-span-5">
              <label className="sm:hidden text-xs text-neutral-500 mb-1 block">课程名称</label>
              <input 
                type="text" 
                placeholder="例如: 高等数学"
                value={course.name}
                onChange={(e) => updateCourse(course.id, 'name', e.target.value)}
                className="w-full px-3 py-2 bg-white border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent transition-shadow text-neutral-900 text-sm"
              />
            </div>
            <div className="col-span-3">
              <label className="sm:hidden text-xs text-neutral-500 mb-1 block">学分</label>
              <input 
                type="number" 
                min="0"
                step="0.5"
                placeholder="学分"
                value={course.credits || ''}
                onChange={(e) => updateCourse(course.id, 'credits', parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 bg-white border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent transition-shadow text-neutral-900 text-sm"
              />
            </div>
            <div className="col-span-3">
              <label className="sm:hidden text-xs text-neutral-500 mb-1 block">成绩</label>
              <input 
                type="number" 
                min="0"
                max="100"
                placeholder="成绩"
                value={course.score || ''}
                onChange={(e) => updateCourse(course.id, 'score', parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 bg-white border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent transition-shadow text-neutral-900 text-sm"
              />
            </div>
            <div className="col-span-1 flex items-end sm:items-center justify-end sm:justify-center mt-2 sm:mt-0">
              <button 
                onClick={() => removeCourse(course.id)}
                disabled={courses.length === 1}
                className="p-2 text-neutral-400 hover:text-semantic-error hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title="删除课程"
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <button 
        onClick={addCourse}
        className="w-full py-3 flex items-center justify-center text-sm font-medium text-brand-blue bg-brand-blue-light border border-dashed border-blue-200 rounded-xl hover:bg-blue-100 transition-colors"
      >
        <Plus className="w-4 h-4 mr-2" />
        添加课程
      </button>
    </div>
  );
};
